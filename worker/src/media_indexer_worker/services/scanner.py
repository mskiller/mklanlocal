from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from media_indexer_backend.core.config import get_settings
from media_indexer_backend.db.session import SessionLocal
from media_indexer_backend.models.enums import MediaType, ScanStatus, SourceStatus
from media_indexer_backend.models.tables import Asset, AssetMetadata, AssetSearch, AssetSimilarity, AssetTag, ScanJob, Source
from media_indexer_backend.services.audit import record_audit_event
from media_indexer_backend.services.metadata import (
    build_search_text,
    build_tags,
    compute_sha256,
    detect_media_type,
    guess_mime_type,
    normalize_metadata,
    parse_datetime,
    should_reextract_metadata,
)
from media_indexer_backend.services.path_safety import validate_source_root
from media_indexer_backend.services.source_service import reconcile_source_statuses
from media_indexer_worker.services.extractors import extract_exiftool, extract_ffprobe
from media_indexer_worker.services.previews import PreviewGenerator
from media_indexer_worker.services.similarity import SimilarityService


logger = logging.getLogger(__name__)


class ScanWorker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.previews = PreviewGenerator()
        self.similarity = SimilarityService()

    def run_forever(self) -> None:
        logger.info("worker loop started")
        while True:
            try:
                processed = self.run_once()
            except Exception as exc:  # noqa: BLE001
                logger.exception("worker loop iteration failed", extra={"error": str(exc)})
                processed = False
            if not processed:
                time.sleep(self.settings.worker_poll_interval_seconds)

    def run_once(self) -> bool:
        with SessionLocal() as session:
            job = session.execute(
                select(ScanJob)
                .where(ScanJob.status == ScanStatus.QUEUED)
                .order_by(ScanJob.created_at)
                .with_for_update(skip_locked=True)
            ).scalars().first()
            if not job:
                if reconcile_source_statuses(session):
                    session.commit()
                    return True
                return False

            source = session.get(Source, job.source_id)
            if source is None:
                job.status = ScanStatus.FAILED
                job.message = "Source no longer exists."
                job.finished_at = datetime.now(tz=timezone.utc)
                session.commit()
                return True

            job.status = ScanStatus.RUNNING
            job.started_at = datetime.now(tz=timezone.utc)
            job.message = "Discovering media files..."
            source.status = SourceStatus.SCANNING
            session.commit()
            job_id = job.id

        self.process_job(job_id)
        return True

    def process_job(self, job_id) -> None:
        try:
            with SessionLocal() as session:
                job = session.get(ScanJob, job_id)
                if job is None:
                    return
                source = session.get(Source, job.source_id)
                if source is None:
                    job.status = ScanStatus.FAILED
                    job.message = "Source disappeared before scan."
                    job.finished_at = datetime.now(tz=timezone.utc)
                    session.commit()
                    return

                root = Path(validate_source_root(source.root_path))
                candidates = self._discover_candidates(root)
                existing_assets = {
                    asset.relative_path: asset
                    for asset in session.execute(select(Asset).where(Asset.source_id == source.id)).scalars().all()
                }
                discovered_paths: set[str] = set()
                total = len(candidates)

                record_audit_event(
                    session,
                    actor="worker",
                    action="scan.started",
                    resource_type="scan_job",
                    resource_id=job.id,
                    details={"source_id": str(source.id), "candidate_count": total},
                )
                session.commit()

                for index, path in enumerate(candidates, start=1):
                    should_stop = False
                    session.expire_all()
                    job = session.get(ScanJob, job_id)
                    if job is None or job.status == ScanStatus.CANCELLED:
                        source = session.get(Source, source.id) if source is not None else None
                        if source is not None:
                            source.status = SourceStatus.READY
                            session.commit()
                        return
                    relative_path = path.relative_to(root).as_posix()
                    discovered_paths.add(relative_path)
                    had_existing = relative_path in existing_assets
                    job.message = f"Scanning {index}/{total}: {relative_path}"
                    session.commit()
                    try:
                        self._process_candidate(session, job, source, path, relative_path, existing_assets)
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("failed to process candidate", extra={"path": str(path), "error": str(exc)})
                        session.rollback()
                        if not had_existing:
                            existing_assets.pop(relative_path, None)
                        job = session.get(ScanJob, job_id)
                        source = session.get(Source, source.id) if source is not None else None
                        if job is not None:
                            job.error_count += 1
                            error_details = list(job.error_details or [])
                            error_details.append(
                                {
                                    "path": str(path),
                                    "error": str(exc),
                                    "at": datetime.now(tz=timezone.utc).isoformat(),
                                }
                            )
                            job.error_details = error_details
                        else:
                            should_stop = True
                    finally:
                        if job is not None:
                            job.scanned_count = index
                            job.progress = int((index / total) * 100) if total else 100
                            session.commit()
                    if should_stop:
                        break

                job.message = "Reconciling deleted files..."
                session.commit()
                deleted_count = self._delete_missing_assets(session, source.id, existing_assets, discovered_paths)
                job.deleted_count += deleted_count
                job.status = ScanStatus.COMPLETED
                job.progress = 100
                job.finished_at = datetime.now(tz=timezone.utc)
                job.message = (
                    f"Scan complete. scanned={job.scanned_count} new={job.new_count} "
                    f"updated={job.updated_count} deleted={job.deleted_count} errors={job.error_count}"
                )
                source.status = SourceStatus.READY
                source.last_scan_at = datetime.now(tz=timezone.utc)
                record_audit_event(
                    session,
                    actor="worker",
                    action="scan.completed",
                    resource_type="scan_job",
                    resource_id=job.id,
                    details={
                        "source_id": str(source.id),
                        "new_count": job.new_count,
                        "updated_count": job.updated_count,
                        "deleted_count": job.deleted_count,
                        "error_count": job.error_count,
                    },
                )
                session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("scan job failed", extra={"job_id": str(job_id), "error": str(exc)})
            with SessionLocal() as session:
                job = session.get(ScanJob, job_id)
                if job is not None:
                    source = session.get(Source, job.source_id)
                    job.status = ScanStatus.FAILED
                    job.message = str(exc)
                    job.finished_at = datetime.now(tz=timezone.utc)
                    if source is not None:
                        source.status = SourceStatus.ERROR
                    record_audit_event(
                        session,
                        actor="worker",
                        action="scan.failed",
                        resource_type="scan_job",
                        resource_id=job.id,
                        details={"error": str(exc)},
                    )
                    session.commit()

    def _discover_candidates(self, root: Path) -> list[Path]:
        candidates: list[Path] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            media_type = detect_media_type(path, guess_mime_type(path))
            if media_type == MediaType.UNKNOWN:
                continue
            candidates.append(path)
        return candidates

    def _process_candidate(
        self,
        session,
        job: ScanJob,
        source: Source,
        path: Path,
        relative_path: str,
        existing_assets: dict[str, Asset],
    ) -> None:
        stat = path.stat()
        mime_type = guess_mime_type(path)
        media_type = detect_media_type(path, mime_type)
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        filesystem_created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
        existing = existing_assets.get(relative_path)
        existing_metadata_record = session.get(AssetMetadata, existing.id) if existing else None
        content_changed = not (
            existing
            and existing.size_bytes == stat.st_size
            and existing.modified_at == modified_at
        )
        needs_metadata_refresh = should_reextract_metadata(
            existing_size_bytes=existing.size_bytes if existing else None,
            existing_modified_at=existing.modified_at if existing else None,
            existing_normalized_json=existing_metadata_record.normalized_json if existing_metadata_record else None,
            file_size_bytes=stat.st_size,
            file_modified_at=modified_at,
        )

        if existing and not needs_metadata_refresh:
            return

        if job.message != f"Extracting metadata: {relative_path}":
            job.message = f"Extracting metadata: {relative_path}"
            session.commit()

        checksum = existing.checksum if existing and not content_changed and existing.checksum else compute_sha256(path)
        exif = extract_exiftool(path)
        ffprobe = extract_ffprobe(path) if media_type == MediaType.VIDEO else {}
        normalized = normalize_metadata(media_type=media_type, exif=exif, ffprobe=ffprobe)
        created_at = parse_datetime(normalized.get("created_at")) or filesystem_created_at

        if existing:
            asset = existing
            asset.filename = path.name
            asset.extension = path.suffix.lower()
            asset.media_type = media_type
            asset.mime_type = mime_type
            asset.size_bytes = stat.st_size
            asset.checksum = checksum
            asset.modified_at = modified_at
            asset.created_at = created_at
            asset.indexed_at = datetime.now(tz=timezone.utc)
        else:
            asset = Asset(
                source_id=source.id,
                relative_path=relative_path,
                filename=path.name,
                extension=path.suffix.lower(),
                media_type=media_type,
                mime_type=mime_type,
                size_bytes=stat.st_size,
                checksum=checksum,
                modified_at=modified_at,
                created_at=created_at,
                indexed_at=datetime.now(tz=timezone.utc),
            )
            session.add(asset)
            existing_assets[relative_path] = asset

        session.flush()
        if existing:
            job.updated_count += 1
        else:
            job.new_count += 1

        session.execute(delete(AssetTag).where(AssetTag.asset_id == asset.id))

        metadata_record = session.get(AssetMetadata, asset.id)
        raw_json = {"exiftool": exif, "ffprobe": ffprobe}
        if metadata_record:
            metadata_record.raw_json = raw_json
            metadata_record.normalized_json = normalized
            metadata_record.extracted_at = datetime.now(tz=timezone.utc)
        else:
            session.add(
                AssetMetadata(
                    asset_id=asset.id,
                    raw_json=raw_json,
                    normalized_json=normalized,
                    extracted_at=datetime.now(tz=timezone.utc),
                )
            )

        tags = build_tags(normalized, exif)
        if tags:
            session.add_all([AssetTag(asset_id=asset.id, tag=tag) for tag in tags])

        search_text = build_search_text(asset.filename, asset.relative_path, normalized, tags)
        session.execute(
            insert(AssetSearch)
            .values(asset_id=asset.id, document=func.to_tsvector("simple", search_text))
            .on_conflict_do_update(
                index_elements=[AssetSearch.asset_id],
                set_={"document": func.to_tsvector("simple", search_text)},
            )
        )

        preview_root = self.settings.preview_root_path
        preview_exists = bool(asset.preview_path and (preview_root / asset.preview_path).exists())
        if content_changed or not preview_exists or (media_type == MediaType.IMAGE and not asset.blur_hash):
            job.message = f"Generating preview: {relative_path}"
            session.commit()
            asset.preview_path, asset.blur_hash = self.previews.generate(asset.id, media_type, path)

        similarity_record = session.get(AssetSimilarity, asset.id) if media_type == MediaType.IMAGE else None
        needs_similarity_refresh = (
            media_type == MediaType.IMAGE
            and (
                content_changed
                or similarity_record is None
                or similarity_record.phash is None
                or (self.settings.clip_enabled and similarity_record.embedding is None)
            )
        )
        if needs_similarity_refresh:
            job.message = f"Computing similarity: {relative_path}"
            session.commit()
            self.similarity.refresh(session, asset.id, path)
        elif media_type == MediaType.IMAGE:
            self.similarity.refresh_tag_links(session, asset.id)
        session.commit()

    def _delete_missing_assets(
        self,
        session,
        source_id,
        existing_assets: dict[str, Asset],
        discovered_paths: set[str],
    ) -> int:
        deleted_count = 0
        for relative_path, asset in list(existing_assets.items()):
            if relative_path in discovered_paths:
                continue
            self.previews.cleanup(asset.id, asset.preview_path)
            session.delete(asset)
            deleted_count += 1
        session.commit()
        return deleted_count
