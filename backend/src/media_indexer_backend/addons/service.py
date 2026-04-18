from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from PIL import Image
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from media_indexer_backend.addons.models import AddonArtifact, AddonJob, AddonPreset
from media_indexer_backend.addons.registry import AddonDefinition, AddonExecutionContext, GeneratedArtifact, get_addon_definition
from media_indexer_backend.addons.schemas import AddonArtifactRead, AddonJobCreate, AddonJobRead, AddonPresetCreate, AddonPresetRead, AddonPresetUpdate
from media_indexer_backend.core.config import get_settings
from media_indexer_backend.models.tables import Asset, Collection, CollectionAsset, User
from media_indexer_backend.platform.registry import discover_manifest_map, ensure_runtime_import_paths
from media_indexer_backend.platform.service import ensure_module_enabled as ensure_platform_module_enabled, get_live_module_setting
from media_indexer_backend.services.asset_service import _allowed_source_ids, _apply_source_scope
from media_indexer_backend.services.inbox_service import _upload_source, ingest_generated_file_to_inbox


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _module_settings(module_id: str) -> dict[str, Any]:
    manifest = discover_manifest_map().get(module_id)
    if manifest is None:
        return {}
    settings: dict[str, Any] = {}
    for field in manifest.settings_fields:
        settings[field.key] = get_live_module_setting(module_id, field.key, field.default)
    return settings


def _artifact_storage_root() -> Path:
    return get_settings().preview_root_path / "addons"


def _artifact_file_path(module_id: str, artifact_id: UUID, filename: str) -> Path:
    return _artifact_storage_root() / module_id / f"{artifact_id.hex}-{filename}"


def _params_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _ensure_definition_registered(module_id: str) -> AddonDefinition:
    definition = get_addon_definition(module_id)
    if definition is not None:
        return definition

    manifest = discover_manifest_map().get(module_id)
    if manifest is None or not manifest.backend_entrypoint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Addon {module_id!r} is not installed.")

    ensure_runtime_import_paths("backend")
    if ":" in manifest.backend_entrypoint:
        module_name, attribute = manifest.backend_entrypoint.split(":", 1)
        module = __import__(module_name, fromlist=[attribute])
        value = getattr(module, attribute)
        if callable(value):
            value()
    else:
        __import__(manifest.backend_entrypoint)

    definition = get_addon_definition(module_id)
    if definition is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Addon {module_id!r} did not register correctly.")
    return definition


def _preset_read(preset: AddonPreset) -> AddonPresetRead:
    return AddonPresetRead(
        id=preset.id,
        module_id=preset.module_id,
        name=preset.name,
        description=preset.description,
        version=preset.version,
        is_builtin=preset.is_builtin,
        config_json=preset.config_json or {},
        created_by=preset.created_by,
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


def _artifact_read(artifact: AddonArtifact) -> AddonArtifactRead:
    return AddonArtifactRead(
        id=artifact.id,
        module_id=artifact.module_id,
        job_id=artifact.job_id,
        asset_id=artifact.asset_id,
        preset_id=artifact.preset_id,
        status=artifact.status,
        label=artifact.label,
        filename=artifact.filename,
        mime_type=artifact.mime_type,
        size_bytes=artifact.size_bytes,
        width=artifact.width,
        height=artifact.height,
        source_checksum=artifact.source_checksum,
        params_hash=artifact.params_hash,
        recipe_version=artifact.recipe_version,
        metadata_json=artifact.metadata_json or {},
        content_url=f"/modules/{artifact.module_id}/artifacts/{artifact.id}/content",
        promoted_inbox_path=artifact.promoted_inbox_path,
        promoted_at=artifact.promoted_at,
        created_at=artifact.created_at,
    )


def _job_read(job: AddonJob) -> AddonJobRead:
    artifacts = sorted(job.artifacts, key=lambda item: item.created_at)
    return AddonJobRead(
        id=job.id,
        module_id=job.module_id,
        created_by=job.created_by,
        preset_id=job.preset_id,
        scope_type=job.scope_type,
        scope_json=job.scope_json or {},
        params_json=job.params_json or {},
        status=job.status,
        progress=job.progress,
        message=job.message,
        error_message=job.error_message,
        artifact_count=len(artifacts),
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        artifacts=[_artifact_read(item) for item in artifacts],
    )


def _ensure_default_presets(session: Session, definition: AddonDefinition) -> None:
    existing = {
        preset.name: preset
        for preset in session.execute(select(AddonPreset).where(AddonPreset.module_id == definition.module_id)).scalars()
    }
    changed = False
    for seed in definition.default_presets:
        preset = existing.get(seed.name)
        if preset is None:
            session.add(
                AddonPreset(
                    module_id=definition.module_id,
                    name=seed.name,
                    description=seed.description,
                    version=seed.version,
                    is_builtin=True,
                    config_json=seed.config_json,
                )
            )
            changed = True
            continue
        if not preset.is_builtin:
            continue
        if preset.description != seed.description or preset.version != seed.version or (preset.config_json or {}) != seed.config_json:
            preset.description = seed.description
            preset.version = seed.version
            preset.config_json = seed.config_json
            changed = True
    if changed:
        session.flush()


def _normalized_preset_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Preset name cannot be empty.")
    return normalized


def list_presets(session: Session, module_id: str) -> list[AddonPresetRead]:
    ensure_platform_module_enabled(session, module_id)
    definition = _ensure_definition_registered(module_id)
    _ensure_default_presets(session, definition)
    presets = session.execute(
        select(AddonPreset).where(AddonPreset.module_id == module_id).order_by(AddonPreset.is_builtin.desc(), AddonPreset.name)
    ).scalars().all()
    return [_preset_read(item) for item in presets]


def create_preset(session: Session, module_id: str, payload: AddonPresetCreate, *, current_user: User) -> AddonPresetRead:
    ensure_platform_module_enabled(session, module_id)
    definition = _ensure_definition_registered(module_id)
    _ensure_default_presets(session, definition)
    normalized_name = _normalized_preset_name(payload.name)
    existing = session.execute(
        select(AddonPreset).where(AddonPreset.module_id == module_id, AddonPreset.name == normalized_name)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A preset with that name already exists.")
    preset = AddonPreset(
        module_id=module_id,
        name=normalized_name,
        description=payload.description,
        version=1,
        is_builtin=False,
        config_json=payload.config_json,
        created_by=current_user.id,
    )
    session.add(preset)
    session.flush()
    return _preset_read(preset)


def update_preset(session: Session, module_id: str, preset_id: UUID, payload: AddonPresetUpdate) -> AddonPresetRead:
    ensure_platform_module_enabled(session, module_id)
    definition = _ensure_definition_registered(module_id)
    _ensure_default_presets(session, definition)
    preset = session.get(AddonPreset, preset_id)
    if preset is None or preset.module_id != module_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preset not found.")
    if preset.is_builtin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Built-in presets are read-only.")
    original_config = preset.config_json or {}
    if payload.name is not None:
        normalized_name = _normalized_preset_name(payload.name)
        existing = session.execute(
            select(AddonPreset).where(
                AddonPreset.module_id == module_id,
                AddonPreset.name == normalized_name,
                AddonPreset.id != preset.id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A preset with that name already exists.")
        preset.name = normalized_name
    if payload.description is not None:
        preset.description = payload.description
    if payload.config_json is not None:
        preset.config_json = payload.config_json
        if payload.config_json != original_config:
            preset.version += 1
    session.flush()
    return _preset_read(preset)


def _query_assets(session: Session, asset_ids: list[UUID], *, current_user: User) -> list[Asset]:
    query = (
        select(Asset)
        .where(Asset.id.in_(asset_ids))
        .options(selectinload(Asset.metadata_record), selectinload(Asset.source))
    )
    query = _apply_source_scope(query, _allowed_source_ids(session, current_user))
    assets = session.execute(query).scalars().all()
    if len(assets) != len({asset_id for asset_id in asset_ids}):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more assets were not found.")
    return assets


def _resolve_scope(
    session: Session,
    module_id: str,
    payload: AddonJobCreate,
    *,
    current_user: User,
    definition: AddonDefinition,
) -> tuple[str, dict[str, Any], list[Asset], Collection | None]:
    provided = int(payload.asset_id is not None) + int(bool(payload.asset_ids)) + int(payload.collection_id is not None)
    if provided != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one scope is required: asset_id, asset_ids, or collection_id.",
        )

    if payload.collection_id is not None:
        if not definition.supports_collection:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{module_id} does not support collection jobs.")
        collection = session.get(Collection, payload.collection_id)
        if collection is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found.")
        asset_ids = list(
            session.execute(
                select(CollectionAsset.asset_id).where(CollectionAsset.collection_id == collection.id)
            ).scalars()
        )
        assets = _query_assets(session, asset_ids, current_user=current_user) if asset_ids else []
        return (
            "collection",
            {"collection_id": str(collection.id), "asset_ids": [str(asset.id) for asset in assets]},
            assets,
            collection,
        )

    if payload.asset_id is not None:
        if not definition.supports_asset:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{module_id} does not support single-asset jobs.")
        assets = _query_assets(session, [payload.asset_id], current_user=current_user)
        return ("asset", {"asset_id": str(assets[0].id)}, assets, None)

    if not definition.supports_batch:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{module_id} does not support batch jobs.")
    if not payload.asset_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="asset_ids cannot be empty.")
    assets = _query_assets(session, payload.asset_ids, current_user=current_user)
    return ("batch", {"asset_ids": [str(asset.id) for asset in assets]}, assets, None)


def _save_generated_artifact(
    session: Session,
    *,
    job: AddonJob,
    preset: AddonPreset | None,
    generated: GeneratedArtifact,
    params_hash: str,
    recipe_version: int,
    source_checksum: str | None,
    artifact_metadata: dict[str, Any] | None = None,
    cache_hit: bool = False,
) -> AddonArtifact:
    artifact = AddonArtifact(
        module_id=job.module_id,
        job_id=job.id,
        asset_id=UUID(str(generated.asset_id)) if generated.asset_id else None,
        preset_id=preset.id if preset else None,
        status="ready",
        label=generated.label,
        filename=generated.filename,
        mime_type=generated.mime_type,
        storage_path="",
        size_bytes=len(generated.content),
        width=generated.width,
        height=generated.height,
        source_checksum=source_checksum,
        params_hash=params_hash,
        recipe_version=recipe_version,
        metadata_json={**(artifact_metadata or {}), **generated.metadata_json, "cache_hit": cache_hit},
    )
    session.add(artifact)
    session.flush()

    output_path = _artifact_file_path(job.module_id, artifact.id, artifact.filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(generated.content)
    artifact.storage_path = str(output_path)
    session.flush()
    return artifact


def _dimensions_from_bytes(content: bytes) -> tuple[int | None, int | None]:
    try:
        from io import BytesIO

        with Image.open(BytesIO(content)) as image:
            return image.width, image.height
    except Exception:  # noqa: BLE001
        return None, None


def _clone_cached_artifact(
    session: Session,
    *,
    job: AddonJob,
    preset: AddonPreset | None,
    cached: AddonArtifact,
) -> AddonArtifact:
    clone = AddonArtifact(
        module_id=job.module_id,
        job_id=job.id,
        asset_id=cached.asset_id,
        preset_id=preset.id if preset else cached.preset_id,
        status="ready",
        label=cached.label,
        filename=cached.filename,
        mime_type=cached.mime_type,
        storage_path=cached.storage_path,
        size_bytes=cached.size_bytes,
        width=cached.width,
        height=cached.height,
        source_checksum=cached.source_checksum,
        params_hash=cached.params_hash,
        recipe_version=cached.recipe_version,
        metadata_json={**(cached.metadata_json or {}), "cache_hit": True},
    )
    session.add(clone)
    session.flush()
    return clone


def _cached_artifact(
    session: Session,
    *,
    module_id: str,
    asset: Asset,
    params_hash: str,
    recipe_version: int,
) -> AddonArtifact | None:
    artifact = session.execute(
        select(AddonArtifact)
        .where(
            AddonArtifact.module_id == module_id,
            AddonArtifact.asset_id == asset.id,
            AddonArtifact.params_hash == params_hash,
            AddonArtifact.source_checksum == asset.checksum,
            AddonArtifact.recipe_version == recipe_version,
            AddonArtifact.status == "ready",
        )
        .order_by(desc(AddonArtifact.created_at))
    ).scalar_one_or_none()
    if artifact is None:
        return None
    if not Path(artifact.storage_path).exists():
        return None
    return artifact


def _execute_job(
    session: Session,
    *,
    job: AddonJob,
    definition: AddonDefinition,
    current_user: User,
    assets: list[Asset],
    collection: Collection | None,
    preset: AddonPreset | None,
    params_json: dict[str, Any],
) -> None:
    module_settings = _module_settings(job.module_id)
    recipe_version = preset.version if preset is not None else 1
    context = AddonExecutionContext(
        session=session,
        current_user=current_user,
        module_id=job.module_id,
        module_settings=module_settings,
        params_json=params_json,
        scope_type=job.scope_type,
        scope_json=job.scope_json or {},
        assets=assets,
        collection=collection,
        preset=preset,
        recipe_version=recipe_version,
    )

    params_hash = _params_hash(params_json)
    job.status = "running"
    job.started_at = utcnow()
    job.progress = 0
    job.message = "Processing addon job..."
    session.flush()

    created_count = 0

    if definition.per_asset_processor is not None and job.scope_type in {"asset", "batch"}:
        for index, asset in enumerate(assets, start=1):
            cached = _cached_artifact(
                session,
                module_id=job.module_id,
                asset=asset,
                params_hash=params_hash,
                recipe_version=recipe_version,
            )
            if cached is not None:
                _clone_cached_artifact(session, job=job, preset=preset, cached=cached)
                created_count += 1
                job.progress = int((index / max(len(assets), 1)) * 100)
                job.message = f"Reused cached artifact {index}/{len(assets)}."
                session.flush()
                continue

            generated_artifacts = definition.per_asset_processor(context, asset)
            for generated in generated_artifacts:
                width, height = generated.width, generated.height
                if width is None or height is None:
                    width, height = _dimensions_from_bytes(generated.content)
                    generated.width = width
                    generated.height = height
                _save_generated_artifact(
                    session,
                    job=job,
                    preset=preset,
                    generated=generated,
                    params_hash=params_hash,
                    recipe_version=recipe_version,
                    source_checksum=asset.checksum,
                )
                created_count += 1
            job.progress = int((index / max(len(assets), 1)) * 100)
            job.message = f"Processed {index}/{len(assets)} assets."
            session.flush()
    elif definition.job_processor is not None:
        generated_artifacts = definition.job_processor(context)
        for generated in generated_artifacts:
            width, height = generated.width, generated.height
            if width is None or height is None:
                width, height = _dimensions_from_bytes(generated.content)
                generated.width = width
                generated.height = height
            _save_generated_artifact(
                session,
                job=job,
                preset=preset,
                generated=generated,
                params_hash=params_hash,
                recipe_version=recipe_version,
                source_checksum=None,
            )
            created_count += 1
        job.progress = 100
        job.message = f"Created {created_count} artifacts."
        session.flush()
    else:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{job.module_id} has no processor configured.")

    job.status = "completed"
    job.progress = 100
    job.finished_at = utcnow()
    job.message = job.message or f"Created {created_count} artifacts."
    session.flush()


def create_job(session: Session, module_id: str, payload: AddonJobCreate, *, current_user: User) -> AddonJobRead:
    ensure_platform_module_enabled(session, module_id)
    definition = _ensure_definition_registered(module_id)
    _ensure_default_presets(session, definition)

    preset = None
    if payload.preset_id is not None:
        preset = session.get(AddonPreset, payload.preset_id)
        if preset is None or preset.module_id != module_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preset not found.")

    scope_type, scope_json, assets, collection = _resolve_scope(
        session,
        module_id,
        payload,
        current_user=current_user,
        definition=definition,
    )
    merged_params = {**(preset.config_json if preset is not None else {}), **(payload.params_json or {})}

    job = AddonJob(
        module_id=module_id,
        created_by=current_user.id,
        preset_id=preset.id if preset is not None else None,
        scope_type=scope_type,
        scope_json=scope_json,
        params_json=merged_params,
        status="queued",
        progress=0,
        message="Queued addon job.",
    )
    session.add(job)
    session.flush()

    try:
        _execute_job(
            session,
            job=job,
            definition=definition,
            current_user=current_user,
            assets=assets,
            collection=collection,
            preset=preset,
            params_json=merged_params,
        )
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = utcnow()
        job.message = "Addon job failed."
        session.flush()

    job = session.execute(
        select(AddonJob)
        .where(AddonJob.id == job.id)
        .options(selectinload(AddonJob.artifacts))
    ).scalar_one()
    return _job_read(job)


def get_job(session: Session, module_id: str, job_id: UUID, *, current_user: User) -> AddonJobRead:
    ensure_platform_module_enabled(session, module_id)
    job = session.execute(
        select(AddonJob)
        .where(AddonJob.id == job_id, AddonJob.module_id == module_id, AddonJob.created_by == current_user.id)
        .options(selectinload(AddonJob.artifacts))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Addon job not found.")
    return _job_read(job)


def list_jobs(session: Session, module_id: str, *, current_user: User, limit: int = 20) -> list[AddonJobRead]:
    ensure_platform_module_enabled(session, module_id)
    jobs = session.execute(
        select(AddonJob)
        .where(AddonJob.module_id == module_id, AddonJob.created_by == current_user.id)
        .options(selectinload(AddonJob.artifacts))
        .order_by(desc(AddonJob.created_at))
        .limit(limit)
    ).scalars().all()
    return [_job_read(job) for job in jobs]


def list_asset_artifacts(session: Session, module_id: str, asset_id: UUID, *, current_user: User) -> list[AddonArtifactRead]:
    ensure_platform_module_enabled(session, module_id)
    _query_assets(session, [asset_id], current_user=current_user)
    artifacts = session.execute(
        select(AddonArtifact)
        .join(AddonJob, AddonJob.id == AddonArtifact.job_id)
        .where(
            AddonArtifact.module_id == module_id,
            AddonArtifact.asset_id == asset_id,
            AddonJob.created_by == current_user.id,
        )
        .order_by(desc(AddonArtifact.created_at))
    ).scalars().all()
    return [_artifact_read(item) for item in artifacts]


def get_artifact_or_404(session: Session, module_id: str, artifact_id: UUID, *, current_user: User | None = None) -> AddonArtifact:
    ensure_platform_module_enabled(session, module_id)
    query = select(AddonArtifact).where(AddonArtifact.id == artifact_id, AddonArtifact.module_id == module_id)
    if current_user is not None:
        query = query.join(AddonJob, AddonJob.id == AddonArtifact.job_id).where(AddonJob.created_by == current_user.id)
    artifact = session.execute(query).scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Addon artifact not found.")
    return artifact


def promote_artifact_to_draft(
    session: Session,
    module_id: str,
    artifact_id: UUID,
    *,
    current_user: User,
    folder: str | None,
):
    artifact = get_artifact_or_404(session, module_id, artifact_id, current_user=current_user)
    artifact_path = Path(artifact.storage_path).resolve(strict=False)
    if not artifact_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file is no longer available.")
    upload_source = _upload_source(session)
    inbox_item = ingest_generated_file_to_inbox(
        session,
        folder=folder or module_id,
        filename=artifact.filename,
        content=artifact_path.read_bytes(),
    )
    artifact.promoted_inbox_path = inbox_item.inbox_path
    artifact.promoted_at = utcnow()
    session.flush()
    return {
        "source_id": upload_source.id,
        "folder": folder or module_id,
        "uploaded_files": [inbox_item.inbox_path],
        "scan_job_id": None,
    }
