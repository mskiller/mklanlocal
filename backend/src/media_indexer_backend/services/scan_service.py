from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from media_indexer_backend.models.enums import ScanStatus, SourceStatus
from media_indexer_backend.models.tables import ScanJob, Source
from media_indexer_backend.services.source_service import get_source_or_404, reconcile_source_statuses

TERMINAL_SCAN_STATUSES = (
    ScanStatus.COMPLETED,
    ScanStatus.FAILED,
    ScanStatus.CANCELLED,
)


def queue_scan(session: Session, source_id) -> ScanJob:
    reconcile_source_statuses(session)
    source = get_source_or_404(session, source_id)
    if source.status == SourceStatus.SCANNING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This source is already scanning or finishing a cancellation request.",
        )
    existing = session.execute(
        select(ScanJob).where(
            ScanJob.source_id == source_id,
            ScanJob.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING]),
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    job = ScanJob(source_id=source_id, status=ScanStatus.QUEUED)
    session.add(job)
    session.flush()
    return job


def cancel_scan_job(session: Session, job_id) -> ScanJob:
    job = get_scan_job_or_404(session, job_id)
    if job.status in TERMINAL_SCAN_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only queued or running jobs can be cancelled.")

    was_running = job.status == ScanStatus.RUNNING
    job.status = ScanStatus.CANCELLED
    job.finished_at = datetime.now(tz=timezone.utc)
    job.message = "Scan cancellation requested by admin." if was_running else "Queued scan cancelled by admin."

    source = session.get(Source, job.source_id)
    if source is not None:
        source.status = SourceStatus.SCANNING if was_running else SourceStatus.READY
    session.flush()
    return job


def list_scan_jobs(session: Session, limit: int = 50) -> list[ScanJob]:
    return session.execute(select(ScanJob).order_by(desc(ScanJob.created_at)).limit(limit)).scalars().all()


def clear_terminal_scan_jobs(session: Session) -> int:
    terminal_jobs = (
        session.execute(select(ScanJob).where(ScanJob.status.in_(TERMINAL_SCAN_STATUSES))).scalars().all()
    )
    for job in terminal_jobs:
        session.delete(job)
    session.flush()
    return len(terminal_jobs)


def get_scan_job_or_404(session: Session, job_id) -> ScanJob:
    job = session.get(ScanJob, job_id)
    if not job:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan job not found.")
    return job
