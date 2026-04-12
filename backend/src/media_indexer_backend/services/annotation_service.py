from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from media_indexer_backend.models.tables import Asset, AssetAnnotation, User
from media_indexer_backend.schemas.asset import BulkAnnotateRequest


def get_or_create_annotation(session: Session, asset_id, user_id) -> AssetAnnotation:
    annotation = session.execute(
        select(AssetAnnotation).where(AssetAnnotation.asset_id == asset_id, AssetAnnotation.user_id == user_id)
    ).scalar_one_or_none()
    if annotation is not None:
        return annotation
    annotation = AssetAnnotation(asset_id=asset_id, user_id=user_id)
    session.add(annotation)
    session.flush()
    return annotation


def bulk_annotate_assets(session: Session, payload: BulkAnnotateRequest, current_user: User) -> None:
    assets = session.execute(select(Asset.id).where(Asset.id.in_(payload.asset_ids))).scalars().all()
    asset_ids = set(assets)
    for asset_id in payload.asset_ids:
        if asset_id not in asset_ids:
            continue
        annotation = get_or_create_annotation(session, asset_id, current_user.id)
        if payload.rating is not None:
            annotation.rating = payload.rating
        if payload.review_status is not None:
            annotation.review_status = payload.review_status
        if payload.flagged is not None:
            annotation.flagged = payload.flagged
        if payload.note:
            annotation.note = f"{annotation.note}\n\n{payload.note}".strip() if annotation.note else payload.note
    session.flush()
