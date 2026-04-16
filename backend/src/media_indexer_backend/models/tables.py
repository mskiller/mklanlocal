from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SqlEnum

from media_indexer_backend.db.base import Base
from media_indexer_backend.models.enums import (
    MatchType,
    MediaType,
    ReviewStatus,
    ScanStatus,
    SourceStatus,
    SourceType,
    UserRole,
    UserStatus,
)


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def enum_column(enum_cls, name: str) -> SqlEnum:
    return SqlEnum(
        enum_cls,
        name=name,
        values_callable=lambda members: [member.value for member in members],
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    type: Mapped[SourceType] = mapped_column(enum_column(SourceType, "source_type"), default=SourceType.MOUNTED_FS)
    root_path: Mapped[str] = mapped_column(Text, unique=True)
    status: Mapped[SourceStatus] = mapped_column(enum_column(SourceStatus, "source_status"), default=SourceStatus.READY)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    assets: Mapped[list["Asset"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    scan_jobs: Mapped[list["ScanJob"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(enum_column(UserRole, "user_role"), default=UserRole.GUEST)
    status: Mapped[UserStatus] = mapped_column(enum_column(UserStatus, "user_status"), default=UserStatus.ACTIVE)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    created_collections: Mapped[list["Collection"]] = relationship(
        back_populates="creator",
        foreign_keys="Collection.created_by",
    )
    collection_memberships_added: Mapped[list["CollectionAsset"]] = relationship(
        back_populates="added_by_user",
        foreign_keys="CollectionAsset.added_by",
    )
    annotations: Mapped[list["AssetAnnotation"]] = relationship(back_populates="user")
    group_memberships: Mapped[list["UserGroup"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    status: Mapped[ScanStatus] = mapped_column(enum_column(ScanStatus, "scan_status"), default=ScanStatus.QUEUED)
    progress: Mapped[int] = mapped_column(default=0)
    scanned_count: Mapped[int] = mapped_column(default=0)
    new_count: Mapped[int] = mapped_column(default=0)
    updated_count: Mapped[int] = mapped_column(default=0)
    deleted_count: Mapped[int] = mapped_column(default=0)
    error_count: Mapped[int] = mapped_column(default=0)
    error_details: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source: Mapped[Source] = relationship(back_populates="scan_jobs")


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("source_id", "relative_path", name="uq_assets_source_path"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    relative_path: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(255))
    extension: Mapped[str] = mapped_column(String(32))
    media_type: Mapped[MediaType] = mapped_column(enum_column(MediaType, "media_type"), default=MediaType.UNKNOWN)
    mime_type: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum: Mapped[str] = mapped_column(String(128))
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    preview_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    blur_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    
    # Visual Workflow Extraction (v1.8 Expansion)
    visual_workflow_json: Mapped[dict | list | None] = mapped_column(postgresql.JSONB, nullable=True)
    visual_workflow_confidence: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    visual_workflow_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source: Mapped[Source] = relationship(back_populates="assets")
    metadata_record: Mapped["AssetMetadata | None"] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        uselist=False,
    )
    tags: Mapped[list["AssetTag"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    search_record: Mapped["AssetSearch | None"] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        uselist=False,
    )
    similarity: Mapped["AssetSimilarity | None"] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        uselist=False,
    )
    collection_memberships: Mapped[list["CollectionAsset"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )
    annotations: Mapped[list["AssetAnnotation"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )


class AssetMetadata(Base):
    __tablename__ = "asset_metadata"

    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    raw_json: Mapped[dict] = mapped_column(JSONB)
    normalized_json: Mapped[dict] = mapped_column(JSONB)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    asset: Mapped[Asset] = relationship(back_populates="metadata_record")


class AssetTag(Base):
    __tablename__ = "asset_tags"

    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    tag: Mapped[str] = mapped_column(String(255), primary_key=True)

    asset: Mapped[Asset] = relationship(back_populates="tags")


class AssetSearch(Base):
    __tablename__ = "asset_search"

    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    document: Mapped[str] = mapped_column(TSVECTOR)

    asset: Mapped[Asset] = relationship(back_populates="search_record")


class AssetSimilarity(Base):
    __tablename__ = "asset_similarity"

    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    phash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(512), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    asset: Mapped[Asset] = relationship(back_populates="similarity")


class SimilarityLink(Base):
    __tablename__ = "similarity_links"

    asset_id_a: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    asset_id_b: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    match_type: Mapped[MatchType] = mapped_column(enum_column(MatchType, "match_type"), primary_key=True)
    distance: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssetAnnotation(Base):
    __tablename__ = "asset_annotations"
    __table_args__ = (UniqueConstraint("asset_id", "user_id", name="uq_asset_annotations_asset_user"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rating: Mapped[int | None] = mapped_column(nullable=True)
    review_status: Mapped[ReviewStatus] = mapped_column(
        enum_column(ReviewStatus, "review_status"),
        default=ReviewStatus.UNREVIEWED,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    asset: Mapped["Asset"] = relationship(back_populates="annotations")
    user: Mapped["User | None"] = relationship(back_populates="annotations")


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user_memberships: Mapped[list["UserGroup"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )


class UserGroup(Base):
    __tablename__ = "user_groups"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="group_memberships")
    group: Mapped["Group"] = relationship(back_populates="user_memberships")


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    creator: Mapped[User] = relationship(back_populates="created_collections", foreign_keys=[created_by])
    assets: Mapped[list["CollectionAsset"]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan",
    )


class CollectionAsset(Base):
    __tablename__ = "collection_assets"
    __table_args__ = (UniqueConstraint("collection_id", "asset_id", name="uq_collection_assets_collection_asset"),)

    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    collection: Mapped[Collection] = relationship(back_populates="assets")
    asset: Mapped[Asset] = relationship(back_populates="collection_memberships")
    added_by_user: Mapped[User] = relationship(back_populates="collection_memberships_added", foreign_keys=[added_by])


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(255))
    resource_type: Mapped[str] = mapped_column(String(255))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
