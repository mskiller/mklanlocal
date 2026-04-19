from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AddonPresetCreate(BaseModel):
    name: str
    description: str | None = None
    config_json: dict = Field(default_factory=dict)


class AddonPresetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    config_json: dict | None = None


class AddonPresetRead(BaseModel):
    id: UUID
    module_id: str
    name: str
    description: str | None = None
    version: int
    is_builtin: bool
    config_json: dict
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class AddonArtifactRead(BaseModel):
    id: UUID
    module_id: str
    job_id: UUID
    asset_id: UUID | None = None
    preset_id: UUID | None = None
    status: str
    label: str
    filename: str
    mime_type: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    source_checksum: str | None = None
    params_hash: str
    recipe_version: int
    metadata_json: dict
    content_url: str
    promoted_inbox_path: str | None = None
    promoted_at: datetime | None = None
    created_at: datetime


class AddonJobCreate(BaseModel):
    asset_id: UUID | None = None
    asset_ids: list[UUID] = Field(default_factory=list)
    collection_id: UUID | None = None
    preset_id: UUID | None = None
    params_json: dict = Field(default_factory=dict)


class AddonJobRead(BaseModel):
    id: UUID
    module_id: str
    created_by: UUID
    preset_id: UUID | None = None
    scope_type: str
    scope_json: dict
    params_json: dict
    status: str
    progress: int
    message: str | None = None
    error_message: str | None = None
    artifact_count: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    artifacts: list[AddonArtifactRead] = Field(default_factory=list)
