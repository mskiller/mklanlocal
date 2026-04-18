from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, literal, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from media_indexer_backend.models.enums import MediaType
from media_indexer_backend.models.tables import Asset, AssetMetadata, AssetSearch, AssetTag, CharacterCard, Source, User
from media_indexer_backend.schemas.character import (
    CharacterCardDetail,
    CharacterCardListResponse,
    CharacterCardSummary,
    CharacterCardUpdateRequest,
)
from media_indexer_backend.services.asset_service import get_asset_or_404
from media_indexer_backend.services.character_cards import (
    extract_character_card_from_raw_metadata,
    normalize_character_card_payload,
    sync_character_card_record,
    write_character_card_png,
)
from media_indexer_backend.services.extractors import extract_exiftool, extract_png_metadata_from_file
from media_indexer_backend.services.metadata import build_search_text, compute_sha256, normalize_metadata, parse_datetime
from media_indexer_backend.services.path_safety import resolve_asset_path
from media_indexer_backend.services.user_service import capabilities_for_user


def _allowed_source_ids(session: Session, current_user: User | None):
    if current_user is None:
        return None
    allowed = capabilities_for_user(session, current_user).allowed_source_ids
    return None if allowed == "all" else list(allowed)


def _apply_source_scope(query, allowed_source_ids):
    if allowed_source_ids is None:
        return query
    if not allowed_source_ids:
        return query.where(literal(False))
    return query.where(Asset.source_id.in_(allowed_source_ids))


def _summary_from_row(card: CharacterCard, asset: Asset, source: Source) -> CharacterCardSummary:
    return CharacterCardSummary(
        asset_id=asset.id,
        source_id=asset.source_id,
        source_name=source.name,
        filename=asset.filename,
        relative_path=asset.relative_path,
        preview_url=f"/assets/{asset.id}/preview" if asset.preview_path else f"/assets/{asset.id}/content",
        content_url=f"/assets/{asset.id}/content",
        name=card.name,
        creator=card.creator,
        description=card.description,
        spec=card.spec,
        spec_version=card.spec_version,
        tags=list(card.tags_json or []),
        extracted_at=card.extracted_at,
        updated_at=card.updated_at,
    )


def _detail_from_row(card: CharacterCard, asset: Asset, source: Source) -> CharacterCardDetail:
    summary = _summary_from_row(card, asset, source)
    canonical = normalize_character_card_payload(card.card_json) or dict(card.card_json or {})
    data = canonical.get("data") if isinstance(canonical.get("data"), dict) else {}
    return CharacterCardDetail(
        **summary.model_dump(),
        first_message=data.get("first_mes") if isinstance(data.get("first_mes"), str) else canonical.get("first_mes"),
        message_examples=data.get("mes_example") if isinstance(data.get("mes_example"), str) else canonical.get("mes_example"),
        personality=data.get("personality") if isinstance(data.get("personality"), str) else canonical.get("personality"),
        scenario=data.get("scenario") if isinstance(data.get("scenario"), str) else canonical.get("scenario"),
        creator_notes=data.get("creator_notes") if isinstance(data.get("creator_notes"), str) else canonical.get("creatorcomment"),
        system_prompt=data.get("system_prompt") if isinstance(data.get("system_prompt"), str) else None,
        post_history_instructions=data.get("post_history_instructions") if isinstance(data.get("post_history_instructions"), str) else None,
        character_version=data.get("character_version") if isinstance(data.get("character_version"), str) else None,
        alternate_greetings=[item for item in data.get("alternate_greetings", []) if isinstance(item, str)],
        group_only_greetings=[item for item in data.get("group_only_greetings", []) if isinstance(item, str)],
        canonical_card=canonical,
    )


def list_character_cards(
    session: Session,
    *,
    current_user: User | None,
    q: str | None = None,
    creator: str | None = None,
    tag: str | None = None,
    source_id: UUID | None = None,
    page: int = 1,
    page_size: int = 24,
) -> CharacterCardListResponse:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    allowed_source_ids = _allowed_source_ids(session, current_user)

    query = select(CharacterCard, Asset, Source).join(Asset, CharacterCard.asset_id == Asset.id).join(Source, Source.id == Asset.source_id)
    count_query = select(func.count(CharacterCard.asset_id)).select_from(CharacterCard).join(Asset, CharacterCard.asset_id == Asset.id)
    query = _apply_source_scope(query, allowed_source_ids)
    count_query = _apply_source_scope(count_query, allowed_source_ids)

    if source_id is not None:
        query = query.where(Asset.source_id == source_id)
        count_query = count_query.where(Asset.source_id == source_id)

    if q:
        pattern = f"%{q.strip().lower()}%"
        match = or_(
            func.lower(CharacterCard.name).like(pattern),
            func.lower(func.coalesce(CharacterCard.creator, "")).like(pattern),
            func.lower(func.coalesce(CharacterCard.description, "")).like(pattern),
            func.lower(Asset.filename).like(pattern),
        )
        query = query.where(match)
        count_query = count_query.where(match)

    if creator:
        pattern = f"%{creator.strip().lower()}%"
        creator_match = func.lower(func.coalesce(CharacterCard.creator, "")).like(pattern)
        query = query.where(creator_match)
        count_query = count_query.where(creator_match)

    if tag:
        cleaned_tag = tag.strip()
        if cleaned_tag:
            tag_match = CharacterCard.tags_json.contains([cleaned_tag])
            query = query.where(tag_match)
            count_query = count_query.where(tag_match)

    total = session.execute(count_query).scalar_one()
    rows = session.execute(
        query.order_by(CharacterCard.updated_at.desc(), CharacterCard.name, Asset.filename)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return CharacterCardListResponse(
        items=[_summary_from_row(card, asset, source) for card, asset, source in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_character_card_detail(session: Session, asset_id: UUID, *, current_user: User | None) -> CharacterCardDetail:
    asset = get_asset_or_404(session, asset_id, current_user=current_user)
    record = session.execute(
        select(CharacterCard)
        .where(CharacterCard.asset_id == asset.id)
        .options(selectinload(CharacterCard.asset).selectinload(Asset.source))
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character card not found.")
    return _detail_from_row(record, asset, asset.source)


def _clean_list(values: list[str] | None) -> list[str]:
    if values is None:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        cleaned.append(item)
    return cleaned


def _apply_update_to_card(card: dict[str, Any], payload: CharacterCardUpdateRequest) -> dict[str, Any]:
    normalized = normalize_character_card_payload(card) or {"spec": "chara_card_v3", "spec_version": "3.0", "data": {}}
    changes = payload.model_dump(exclude_unset=True)
    data = dict(normalized.get("data") if isinstance(normalized.get("data"), dict) else {})

    def set_text(key: str, value: str | None, *, top_level_key: str | None = None, allow_none: bool = False) -> None:
        if value is None and not allow_none:
            text = ""
        elif value is None:
            text = None
        else:
            text = value.strip()
            if not text and not allow_none:
                text = ""
            if not text and allow_none:
                text = None
        data[key] = text
        if top_level_key:
            normalized[top_level_key] = text

    if "name" in changes:
        set_text("name", changes["name"], top_level_key="name")
    if "description" in changes:
        set_text("description", changes["description"], top_level_key="description")
    if "personality" in changes:
        set_text("personality", changes["personality"], top_level_key="personality")
    if "scenario" in changes:
        set_text("scenario", changes["scenario"], top_level_key="scenario")
    if "first_message" in changes:
        set_text("first_mes", changes["first_message"], top_level_key="first_mes")
    if "message_examples" in changes:
        set_text("mes_example", changes["message_examples"], top_level_key="mes_example")
    if "creator_notes" in changes:
        set_text("creator_notes", changes["creator_notes"], top_level_key="creatorcomment")
    if "system_prompt" in changes:
        set_text("system_prompt", changes["system_prompt"])
    if "post_history_instructions" in changes:
        set_text("post_history_instructions", changes["post_history_instructions"])
    if "creator" in changes:
        set_text("creator", changes["creator"], top_level_key="creator", allow_none=True)
    if "character_version" in changes:
        set_text("character_version", changes["character_version"], allow_none=True)
    if "tags" in changes:
        cleaned_tags = _clean_list(changes["tags"])
        data["tags"] = cleaned_tags
        normalized["tags"] = cleaned_tags
    if "alternate_greetings" in changes:
        data["alternate_greetings"] = _clean_list(changes["alternate_greetings"])
    if "group_only_greetings" in changes:
        data["group_only_greetings"] = _clean_list(changes["group_only_greetings"])

    normalized["data"] = data
    return normalize_character_card_payload(normalized) or normalized


def _refresh_asset_after_character_write(session: Session, asset: Asset, *, source_root: str) -> CharacterCard:
    asset_path = resolve_asset_path(source_root, asset.relative_path)
    stat = asset_path.stat()
    timestamp = datetime.now(tz=timezone.utc)

    raw_metadata = extract_exiftool(asset_path)
    if asset.extension.lower() == ".png":
        for key, value in extract_png_metadata_from_file(asset_path).items():
            raw_metadata.setdefault(key, value)

    normalized = normalize_metadata(media_type=asset.media_type, exif=raw_metadata, ffprobe={})
    character_card = extract_character_card_from_raw_metadata(raw_metadata)
    if character_card is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Character card write-back did not persist embedded data.")

    asset.size_bytes = stat.st_size
    asset.checksum = compute_sha256(asset_path)
    asset.modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    created_at = parse_datetime(normalized.get("created_at"))
    if created_at is not None:
        asset.created_at = created_at
    asset.indexed_at = timestamp

    metadata_record = asset.metadata_record or session.get(AssetMetadata, asset.id)
    if metadata_record is None:
        metadata_record = AssetMetadata(asset_id=asset.id, raw_json={}, normalized_json={})
        asset.metadata_record = metadata_record
        session.add(metadata_record)
    metadata_record.raw_json = {"exiftool": raw_metadata, "ffprobe": {}}
    metadata_record.normalized_json = normalized
    metadata_record.extracted_at = timestamp

    record = sync_character_card_record(session, asset.id, character_card, extracted_at=timestamp)
    if record is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Character card record could not be refreshed.")

    tags = session.execute(select(AssetTag.tag).where(AssetTag.asset_id == asset.id)).scalars().all()
    search_text = build_search_text(asset.filename, asset.relative_path, normalized, tags)
    session.execute(
        insert(AssetSearch)
        .values(asset_id=asset.id, document=func.to_tsvector("simple", search_text))
        .on_conflict_do_update(
            index_elements=[AssetSearch.asset_id],
            set_={"document": func.to_tsvector("simple", search_text)},
        )
    )
    session.flush()
    return record


def update_character_card(
    session: Session,
    asset_id: UUID,
    payload: CharacterCardUpdateRequest,
    *,
    current_user: User | None,
) -> CharacterCardDetail:
    asset = get_asset_or_404(session, asset_id, current_user=current_user)
    if asset.media_type != MediaType.IMAGE or asset.extension.lower() != ".png":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PNG image assets can be edited as SillyTavern cards.")

    asset_path = resolve_asset_path(asset.source.root_path, asset.relative_path)
    existing = session.get(CharacterCard, asset.id)
    if existing is not None:
        current_card = normalize_character_card_payload(existing.card_json) or dict(existing.card_json or {})
    else:
        raw_metadata = extract_exiftool(asset_path)
        for key, value in extract_png_metadata_from_file(asset_path).items():
            raw_metadata.setdefault(key, value)
        current_card = extract_character_card_from_raw_metadata(raw_metadata)
        if current_card is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset does not contain an embedded SillyTavern character card.")

    updated_card = _apply_update_to_card(current_card, payload)
    try:
        write_character_card_png(asset_path, updated_card)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Character card file is not writable: {exc}") from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Unable to update character card PNG: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    record = _refresh_asset_after_character_write(session, asset, source_root=asset.source.root_path)
    return _detail_from_row(record, asset, asset.source)
