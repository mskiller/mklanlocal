from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from media_indexer_backend.api.dependencies import (
    get_session,
    require_authenticated,
    require_curation_access,
    require_enabled_module,
)
from media_indexer_backend.models.tables import User
from media_indexer_backend.schemas.character import (
    CharacterCardDetail,
    CharacterCardListResponse,
    CharacterCardUpdateRequest,
)
from media_indexer_backend.services.audit import record_audit_event
from media_indexer_backend.services.character_service import (
    get_character_card_detail,
    list_character_cards,
    update_character_card,
)


router = APIRouter(tags=["characters"], dependencies=[Depends(require_enabled_module("characters"))])


@router.get("/characters", response_model=CharacterCardListResponse)
def get_characters(
    q: str | None = None,
    creator: str | None = None,
    tag: str | None = None,
    source_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> CharacterCardListResponse:
    return list_character_cards(
        session,
        current_user=current_user,
        q=q,
        creator=creator,
        tag=tag,
        source_id=source_id,
        page=page,
        page_size=page_size,
    )


@router.get("/characters/{asset_id}", response_model=CharacterCardDetail)
def get_character(
    asset_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> CharacterCardDetail:
    return get_character_card_detail(session, asset_id, current_user=current_user)


@router.patch("/characters/{asset_id}", response_model=CharacterCardDetail)
def patch_character(
    asset_id: UUID,
    payload: CharacterCardUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_curation_access),
) -> CharacterCardDetail:
    detail = update_character_card(session, asset_id, payload, current_user=current_user)
    record_audit_event(
        session,
        actor=current_user.username,
        action="character_card.updated",
        resource_type="character_card",
        resource_id=asset_id,
        details={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    session.commit()
    return detail
