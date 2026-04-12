from __future__ import annotations

import io
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from media_indexer_backend.api.dependencies import get_session, require_admin
from media_indexer_backend.core.config import get_settings
from media_indexer_backend.core.rate_limit import enforce_rate_limit
from media_indexer_backend.models.enums import ScanStatus
from media_indexer_backend.models.tables import ScanJob, User
from media_indexer_backend.schemas.admin import (
    AuditLogRead,
    GroupCreateRequest,
    GroupRead,
    GroupUpdateRequest,
    UserCreateRequest,
    UserPasswordResetRequest,
    UserRead,
    UserUpdateRequest,
)
from media_indexer_backend.schemas.maintenance import ResetRequest, ResetResponse
from media_indexer_backend.schemas.settings import AdminSettings, AdminSettingsUpdateRequest, TagSimilarityRebuildResponse
from media_indexer_backend.services.audit import record_audit_event
from media_indexer_backend.services.backup_service import create_backup_archive, restore_backup_sql, validate_backup_archive
from media_indexer_backend.services.maintenance_service import purge_deepzoom_tiles, reset_application_data
from media_indexer_backend.services.search_reindex_service import reindex_search_documents
from media_indexer_backend.services.settings_service import get_admin_settings, update_admin_settings
from media_indexer_backend.services.tag_similarity_service import rebuild_all_tag_similarity
from media_indexer_backend.services.user_service import (
    create_group,
    create_user,
    delete_group,
    group_reads,
    list_audit_logs,
    list_groups,
    list_users,
    set_user_password,
    update_group,
    update_user,
    user_reads,
)


router = APIRouter(prefix="/admin", tags=["admin"])


def _assert_no_active_scans(session: Session) -> None:
    active_scan = session.execute(
        select(ScanJob.id).where(ScanJob.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING]))
    ).scalar_one_or_none()
    if active_scan is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stop active scans before performing this maintenance action.")


@router.post("/reset", response_model=ResetResponse)
def reset_data(
    payload: ResetRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> ResetResponse:
    enforce_rate_limit(
        key=f"admin-reset:{current_user.id}",
        limit=5,
        window_seconds=60,
        detail="Too many destructive admin actions. Please wait a minute.",
    )
    result = reset_application_data(session, delete_sources=payload.mode == "all")
    record_audit_event(
        session,
        actor=current_user.username,
        action=f"admin.reset.{payload.mode}",
        resource_type="maintenance",
        details=result,
    )
    session.commit()
    return ResetResponse(**result)


@router.get("/users", response_model=list[UserRead])
def get_users(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> list[UserRead]:
    return user_reads(list_users(session))


@router.post("/users", response_model=UserRead, status_code=201)
def post_user(
    payload: UserCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> UserRead:
    user = create_user(session, payload)
    record_audit_event(
        session,
        actor=current_user.username,
        action="user.create",
        resource_type="user",
        resource_id=user.id,
        details={"username": user.username, "role": user.role.value},
    )
    session.commit()
    return user_reads([user])[0]


@router.patch("/users/{user_id}", response_model=UserRead)
def patch_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> UserRead:
    user = update_user(session, user_id, payload)
    record_audit_event(
        session,
        actor=current_user.username,
        action="user.update",
        resource_type="user",
        resource_id=user.id,
        details=payload.model_dump(exclude_none=True),
    )
    session.commit()
    return user_reads([user])[0]


@router.post("/users/{user_id}/password", status_code=204)
def post_user_password(
    user_id: UUID,
    payload: UserPasswordResetRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> None:
    user = set_user_password(session, user_id, payload.new_password)
    record_audit_event(
        session,
        actor=current_user.username,
        action="user.password_reset",
        resource_type="user",
        resource_id=user.id,
        details={"username": user.username},
    )
    session.commit()


@router.get("/groups", response_model=list[GroupRead])
def get_groups(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> list[GroupRead]:
    return group_reads(list_groups(session))


@router.post("/groups", response_model=GroupRead, status_code=201)
def post_group(
    payload: GroupCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> GroupRead:
    group = create_group(session, payload)
    record_audit_event(
        session,
        actor=current_user.username,
        action="group.create",
        resource_type="group",
        resource_id=group.id,
        details=payload.model_dump(),
    )
    session.commit()
    return GroupRead.model_validate(group)


@router.patch("/groups/{group_id}", response_model=GroupRead)
def patch_group(
    group_id: UUID,
    payload: GroupUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> GroupRead:
    group = update_group(session, group_id, payload)
    record_audit_event(
        session,
        actor=current_user.username,
        action="group.update",
        resource_type="group",
        resource_id=group.id,
        details=payload.model_dump(exclude_none=True),
    )
    session.commit()
    return GroupRead.model_validate(group)


@router.delete("/groups/{group_id}", status_code=204)
def remove_group(
    group_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> None:
    group = delete_group(session, group_id)
    record_audit_event(
        session,
        actor=current_user.username,
        action="group.delete",
        resource_type="group",
        resource_id=group.id,
        details={"name": group.name},
    )
    session.commit()


@router.get("/audit-logs", response_model=list[AuditLogRead])
def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> list[AuditLogRead]:
    return list_audit_logs(session, limit)


@router.get("/backup", response_class=StreamingResponse)
def get_backup(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> StreamingResponse:
    filename, buffer, manifest = create_backup_archive(session)
    record_audit_event(
        session,
        actor=current_user.username,
        action="admin.backup.create",
        resource_type="maintenance",
        details={"filename": filename, **manifest},
    )
    session.commit()
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/restore")
async def post_restore(
    file: UploadFile = File(...),
    dry_run: bool = Query(default=False),
    confirm: str = Query(default=""),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> dict:
    enforce_rate_limit(
        key=f"admin-restore:{current_user.id}",
        limit=5,
        window_seconds=300,
        detail="Too many restore attempts. Please wait a few minutes.",
    )
    content = await file.read()
    validation, sql_bytes = validate_backup_archive(content)
    if dry_run:
        return validation

    if confirm != "RESTORE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pass confirm=RESTORE to execute a real restore.")
    _assert_no_active_scans(session)
    restore_backup_sql(sql_bytes)
    record_audit_event(
        session,
        actor=current_user.username,
        action="admin.backup.restore",
        resource_type="maintenance",
        details={"manifest": validation.get("manifest", {}), "dry_run": False},
    )
    session.commit()
    return {"status": "restored", **validation}


@router.post("/purge-deepzoom")
def post_purge_deepzoom(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> dict[str, int]:
    enforce_rate_limit(
        key=f"admin-purge-deepzoom:{current_user.id}",
        limit=10,
        window_seconds=300,
        detail="Too many maintenance requests. Please wait a few minutes.",
    )
    result = purge_deepzoom_tiles(get_settings().preview_root_path)
    record_audit_event(
        session,
        actor=current_user.username,
        action="admin.preview.purge_deepzoom",
        resource_type="maintenance",
        details=result,
    )
    session.commit()
    return result


@router.post("/reindex-search")
def post_reindex_search(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> dict[str, int]:
    _assert_no_active_scans(session)
    rebuilt_assets = reindex_search_documents(session)
    record_audit_event(
        session,
        actor=current_user.username,
        action="admin.search.reindex",
        resource_type="maintenance",
        details={"rebuilt_assets": rebuilt_assets},
    )
    session.commit()
    return {"rebuilt_assets": rebuilt_assets}


@router.get("/settings", response_model=AdminSettings)
def get_admin_settings_route(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> AdminSettings:
    return get_admin_settings(session)


@router.patch("/settings", response_model=AdminSettings)
def patch_admin_settings(
    payload: AdminSettingsUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> AdminSettings:
    result = update_admin_settings(session, payload)
    record_audit_event(
        session,
        actor=current_user.username,
        action="admin.settings.update",
        resource_type="app_settings",
        details=payload.model_dump(),
    )
    session.commit()
    return result


@router.post("/settings/rebuild-tag-similarity", response_model=TagSimilarityRebuildResponse)
def post_rebuild_tag_similarity(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> TagSimilarityRebuildResponse:
    rebuilt_assets, rebuilt_links = rebuild_all_tag_similarity(session)
    record_audit_event(
        session,
        actor=current_user.username,
        action="admin.settings.rebuild_tag_similarity",
        resource_type="app_settings",
        details={"rebuilt_assets": rebuilt_assets, "rebuilt_links": rebuilt_links},
    )
    session.commit()
    return TagSimilarityRebuildResponse(rebuilt_assets=rebuilt_assets, rebuilt_links=rebuilt_links)
