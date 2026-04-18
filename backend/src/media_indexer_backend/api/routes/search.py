from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from media_indexer_backend.api.dependencies import get_session, require_authenticated
from media_indexer_backend.models.enums import ReviewStatus
from media_indexer_backend.models.tables import User
from media_indexer_backend.schemas.asset import AssetListResponse
from media_indexer_backend.services.asset_service import _allowed_source_ids, _apply_source_scope, _asset_summary, search_assets
from media_indexer_backend.models.tables import Asset, AssetSimilarity
from media_indexer_backend.services.clip_service import embed_text
from sqlalchemy import select
from sqlalchemy.orm import selectinload


router = APIRouter(tags=["search"])
MIN_DATETIME = datetime.min.replace(tzinfo=timezone.utc)
SUPPORTED_NL_SORTS = {"relevance", "created_at", "indexed_at", "modified_at", "filename"}


def _normalize_nl_sort(sort: str | None) -> str:
    if sort in SUPPORTED_NL_SORTS:
        return sort
    return "relevance"


def _normalize_sort_direction(sort_direction: str | None) -> str:
    return "asc" if sort_direction == "asc" else "desc"


def _semantic_candidate_limit(limit: int, sort: str) -> int:
    if sort == "relevance":
        return limit
    return min(max(limit * 4, 100), 400)


def _semantic_sort_key(asset: Asset, sort: str):
    if sort == "indexed_at":
        return asset.indexed_at or MIN_DATETIME
    if sort == "created_at":
        return asset.created_at or MIN_DATETIME
    if sort == "modified_at":
        return asset.modified_at or MIN_DATETIME
    return (asset.filename or "").lower()


def _sort_semantic_assets(items: list[Asset], *, sort: str, sort_direction: str) -> list[Asset]:
    normalized_sort = _normalize_nl_sort(sort)
    normalized_direction = _normalize_sort_direction(sort_direction)
    if normalized_sort == "relevance":
        return list(reversed(items)) if normalized_direction == "asc" else items
    return sorted(
        items,
        key=lambda asset: _semantic_sort_key(asset, normalized_sort),
        reverse=normalized_direction == "desc",
    )


@router.get("/search", response_model=AssetListResponse)
def search(
    q: str | None = None,
    media_type: str | None = None,
    caption: str | None = None,
    ocr_text: str | None = None,
    camera_make: str | None = None,
    camera_model: str | None = None,
    year: int | None = None,
    width_min: int | None = None,
    width_max: int | None = None,
    height_min: int | None = None,
    height_max: int | None = None,
    duration_min: float | None = None,
    duration_max: float | None = None,
    has_gps: bool | None = None,
    tags: str | None = None,
    auto_tags: str | None = None,
    exclude_tags: str | None = None,
    min_rating: int | None = Query(default=None, ge=1, le=5),
    review_status: ReviewStatus | None = None,
    flagged: bool | None = None,
    sort: str = "relevance",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> AssetListResponse:
    return search_assets(
        session,
        q=q,
        media_type=media_type,
        caption=caption,
        ocr_text=ocr_text,
        camera_make=camera_make,
        camera_model=camera_model,
        year=year,
        width_min=width_min,
        width_max=width_max,
        height_min=height_min,
        height_max=height_max,
        duration_min=duration_min,
        duration_max=duration_max,
        has_gps=has_gps,
        tags=[value.strip() for value in (tags or "").split(",") if value.strip()],
        auto_tags=[value.strip() for value in (auto_tags or "").split(",") if value.strip()],
        exclude_tags=[value.strip() for value in (exclude_tags or "").split(",") if value.strip()],
        min_rating=min_rating,
        review_status=review_status,
        flagged=flagged,
        sort=sort,
        page=page,
        page_size=page_size,
        current_user=current_user,
    )


@router.get("/search/nl", response_model=AssetListResponse)
async def nl_search(
    q: str,
    limit: int = Query(default=50, ge=1, le=200),
    sort: str = "relevance",
    sort_direction: str = "desc",
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> AssetListResponse:
    vector = await embed_text(q)
    if not vector:
        return AssetListResponse(items=[], total=0, page=1, page_size=limit)
    normalized_sort = _normalize_nl_sort(sort)
    normalized_direction = _normalize_sort_direction(sort_direction)
    distance_expr = AssetSimilarity.embedding.cosine_distance(vector)
    query = (
        select(Asset)
        .join(AssetSimilarity, AssetSimilarity.asset_id == Asset.id)
        .where(AssetSimilarity.embedding.is_not(None))
        .options(
            selectinload(Asset.metadata_record),
            selectinload(Asset.tags),
            selectinload(Asset.annotations),
            selectinload(Asset.source),
        )
        .order_by(distance_expr)
        .limit(_semantic_candidate_limit(limit, normalized_sort))
    )
    query = _apply_source_scope(query, _allowed_source_ids(session, current_user))
    items = session.execute(query).scalars().unique().all()
    items = _sort_semantic_assets(items, sort=normalized_sort, sort_direction=normalized_direction)[:limit]
    return AssetListResponse(
        items=[_asset_summary(item, user_id=current_user.id) for item in items],
        total=len(items),
        page=1,
        page_size=limit,
    )
