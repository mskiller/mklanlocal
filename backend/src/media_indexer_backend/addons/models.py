from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from media_indexer_backend.db.base import Base


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class AddonPreset(Base):
    __tablename__ = "addon_presets"
    __table_args__ = (UniqueConstraint("module_id", "name", name="uq_addon_presets_module_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    module_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    jobs: Mapped[list["AddonJob"]] = relationship(back_populates="preset")
    artifacts: Mapped[list["AddonArtifact"]] = relationship(back_populates="preset")


class AddonJob(Base):
    __tablename__ = "addon_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    module_id: Mapped[str] = mapped_column(String(128), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    preset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("addon_presets.id", ondelete="SET NULL"), nullable=True)
    scope_type: Mapped[str] = mapped_column(String(32), index=True)
    scope_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    params_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    preset: Mapped["AddonPreset | None"] = relationship(back_populates="jobs")
    artifacts: Mapped[list["AddonArtifact"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class AddonArtifact(Base):
    __tablename__ = "addon_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    module_id: Mapped[str] = mapped_column(String(128), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("addon_jobs.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True)
    preset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("addon_presets.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ready", index=True)
    label: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    params_hash: Mapped[str] = mapped_column(String(128), index=True)
    recipe_version: Mapped[int] = mapped_column(Integer, default=1)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    promoted_inbox_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped["AddonJob"] = relationship(back_populates="artifacts")
    preset: Mapped["AddonPreset | None"] = relationship(back_populates="artifacts")
