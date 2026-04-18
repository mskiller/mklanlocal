from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from media_indexer_backend.models.enums import ScanStatus


class ScanJobRead(BaseModel):
    id: UUID
    source_id: UUID
    status: ScanStatus
    progress: int
    scanned_count: int
    new_count: int
    updated_count: int
    deleted_count: int
    error_count: int
    message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanJobErrorEntry(BaseModel):
    path: str
    error: str
    at: str
