from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from media_indexer_backend.api.dependencies import get_session, require_authenticated
from media_indexer_backend.models.tables import User
from media_indexer_backend.schemas.asset import AssetListResponse, TagCount
from media_indexer_backend.services.asset_service import get_assets_for_tag, list_tags


router = APIRouter(tags=["tags"])


@router.get("/tags", response_model=list[TagCount])
def get_tags(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> list[TagCount]:
    return list_tags(session, current_user=current_user)


@router.get("/tags/{tag}/assets", response_model=AssetListResponse)
def get_tag_assets(
    tag: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> AssetListResponse:
    return get_assets_for_tag(session, tag, page, page_size, current_user=current_user)
