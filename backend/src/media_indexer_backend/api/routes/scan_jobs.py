from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from media_indexer_backend.api.dependencies import get_session, require_admin, require_authenticated
from media_indexer_backend.models.tables import User
from media_indexer_backend.schemas.scan_job import ScanJobErrorEntry, ScanJobRead
from media_indexer_backend.services.audit import record_audit_event
from media_indexer_backend.services.scan_service import (
    TERMINAL_SCAN_STATUSES,
    cancel_scan_job,
    clear_terminal_scan_jobs,
    get_scan_job_or_404,
    list_scan_jobs,
)


router = APIRouter(prefix="/scan-jobs", tags=["scan-jobs"])


@router.get("", response_model=list[ScanJobRead])
def get_scan_jobs(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> list[ScanJobRead]:
    return [ScanJobRead.model_validate(job) for job in list_scan_jobs(session)]


@router.delete("/done")
def clear_done_jobs(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> dict[str, int]:
    deleted_count = clear_terminal_scan_jobs(session)
    record_audit_event(
        session,
        actor=current_user.username,
        action="scan_jobs.cleared",
        resource_type="scan_job",
        resource_id=None,
        details={"deleted_count": deleted_count},
    )
    session.commit()
    return {"deleted_count": deleted_count}


@router.get("/{job_id}", response_model=ScanJobRead)
def get_scan_job(
    job_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> ScanJobRead:
    return ScanJobRead.model_validate(get_scan_job_or_404(session, job_id))


@router.get("/{job_id}/errors", response_model=list[ScanJobErrorEntry])
def get_scan_job_errors(
    job_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
) -> list[ScanJobErrorEntry]:
    job = get_scan_job_or_404(session, job_id)
    return [ScanJobErrorEntry.model_validate(item) for item in (job.error_details or [])]


@router.get("/{job_id}/stream")
async def stream_scan_job(
    job_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_authenticated),
):
    """SSE endpoint — emits progress events every 1.5 s while job is active."""

    async def event_generator():
        while True:
            # Re-query on each tick so we pick up live updates
            session.expire_all()
            job = session.get(type(get_scan_job_or_404(session, job_id)), job_id)
            if job is None:
                break

            payload = json.dumps({
                "status": job.status,
                "processed": job.scanned_count,
                "total": job.progress,
            })
            yield {"data": payload}

            if job.status in TERMINAL_SCAN_STATUSES:
                break

            await asyncio.sleep(1.5)

    return EventSourceResponse(event_generator())


@router.post("/{job_id}/cancel", response_model=ScanJobRead)
def cancel_scan(
    job_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> ScanJobRead:
    job = cancel_scan_job(session, job_id)
    record_audit_event(
        session,
        actor=current_user.username,
        action="scan.cancelled",
        resource_type="scan_job",
        resource_id=job.id,
        details={"source_id": str(job.source_id)},
    )
    session.commit()
    return ScanJobRead.model_validate(job)
