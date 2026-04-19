from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from media_indexer_backend.addons.schemas import AddonJobCreate, AddonJobRead, AddonPresetCreate, AddonPresetRead, AddonPresetUpdate, AddonArtifactRead
from media_indexer_backend.addons.service import (
    create_job,
    create_preset,
    get_artifact_or_404,
    get_job,
    list_asset_artifacts,
    list_jobs,
    list_presets,
    promote_artifact_to_draft,
    update_preset,
)
from media_indexer_backend.api.dependencies import get_session, require_admin, require_authenticated, require_curator_or_admin, require_upload_access
from media_indexer_backend.schemas.source import SourceUploadRead
from media_indexer_backend.models.tables import User


router = APIRouter(tags=["addon-tools"])


@router.get("/modules/{module_id}/jobs", response_model=list[AddonJobRead])
def get_addon_jobs(
    module_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> list[AddonJobRead]:
    return list_jobs(session, module_id, current_user=current_user, limit=limit)


@router.post("/modules/{module_id}/jobs", response_model=AddonJobRead)
def post_addon_job(
    module_id: str,
    payload: AddonJobCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_curator_or_admin),
) -> AddonJobRead:
    result = create_job(session, module_id, payload, current_user=current_user)
    session.commit()
    return result


@router.get("/modules/{module_id}/jobs/{job_id}", response_model=AddonJobRead)
def get_addon_job(
    module_id: str,
    job_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> AddonJobRead:
    return get_job(session, module_id, job_id, current_user=current_user)


@router.get("/modules/{module_id}/assets/{asset_id}/artifacts", response_model=list[AddonArtifactRead])
def get_addon_asset_artifacts(
    module_id: str,
    asset_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> list[AddonArtifactRead]:
    return list_asset_artifacts(session, module_id, asset_id, current_user=current_user)


@router.get("/modules/{module_id}/artifacts/{artifact_id}/content")
def get_addon_artifact_content(
    module_id: str,
    artifact_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> FileResponse:
    artifact = get_artifact_or_404(session, module_id, artifact_id, current_user=current_user)
    artifact_path = Path(artifact.storage_path).resolve(strict=False)
    if not artifact_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file is no longer available.")
    return FileResponse(artifact_path, media_type=artifact.mime_type, filename=artifact.filename)


@router.post("/modules/{module_id}/artifacts/{artifact_id}/promote", response_model=SourceUploadRead)
def post_addon_artifact_promote(
    module_id: str,
    artifact_id: UUID,
    folder: str | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_upload_access),
) -> SourceUploadRead:
    payload = promote_artifact_to_draft(session, module_id, artifact_id, current_user=current_user, folder=folder)
    session.commit()
    return SourceUploadRead(**payload)


@router.get("/modules/{module_id}/presets", response_model=list[AddonPresetRead])
def get_addon_presets(
    module_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> list[AddonPresetRead]:
    del current_user
    return list_presets(session, module_id)


@router.post("/modules/{module_id}/presets", response_model=AddonPresetRead)
def post_addon_preset(
    module_id: str,
    payload: AddonPresetCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> AddonPresetRead:
    result = create_preset(session, module_id, payload, current_user=current_user)
    session.commit()
    return result


@router.patch("/modules/{module_id}/presets/{preset_id}", response_model=AddonPresetRead)
def patch_addon_preset(
    module_id: str,
    preset_id: UUID,
    payload: AddonPresetUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> AddonPresetRead:
    del current_user
    result = update_preset(session, module_id, preset_id, payload)
    session.commit()
    return result
