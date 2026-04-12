from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from media_indexer_backend.models.tables import AuditLog


def record_audit_event(
    session: Session,
    *,
    actor: str,
    action: str,
    resource_type: str,
    resource_id: UUID | None = None,
    details: dict | None = None,
) -> None:
    session.add(
        AuditLog(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )
    )

