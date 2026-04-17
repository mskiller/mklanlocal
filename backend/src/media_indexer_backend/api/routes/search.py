from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from media_indexer_backend.api.dependencies import get_session, require_authenticated
from media_indexer_backend.models.enums import ReviewStatus
from media_indexer_backend.models.tables import User
from media_indexer_backend.schemas.asset import AssetListResponse
from media_indexer_backend.services.asset_service import search_assets


router = APIRouter(tags=["search"])


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
