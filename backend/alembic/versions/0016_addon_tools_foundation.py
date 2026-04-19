"""addon tools foundation

Revision ID: 0016_addon_tools_foundation
Revises: 0015_platform_modules
Create Date: 2026-04-19 15:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0016_addon_tools_foundation"
down_revision = "0015_platform_modules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "addon_presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("module_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("module_id", "name", name="uq_addon_presets_module_name"),
    )
    op.create_index("ix_addon_presets_module_id", "addon_presets", ["module_id"])

    op.create_table(
        "addon_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("module_id", sa.String(length=128), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("addon_presets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_addon_jobs_module_id", "addon_jobs", ["module_id"])
    op.create_index("ix_addon_jobs_created_by", "addon_jobs", ["created_by"])
    op.create_index("ix_addon_jobs_scope_type", "addon_jobs", ["scope_type"])
    op.create_index("ix_addon_jobs_status", "addon_jobs", ["status"])

    op.create_table(
        "addon_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("module_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("addon_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("preset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("addon_presets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("source_checksum", sa.String(length=128), nullable=True),
        sa.Column("params_hash", sa.String(length=128), nullable=False),
        sa.Column("recipe_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("promoted_inbox_path", sa.Text(), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_addon_artifacts_module_id", "addon_artifacts", ["module_id"])
    op.create_index("ix_addon_artifacts_job_id", "addon_artifacts", ["job_id"])
    op.create_index("ix_addon_artifacts_asset_id", "addon_artifacts", ["asset_id"])
    op.create_index("ix_addon_artifacts_status", "addon_artifacts", ["status"])
    op.create_index("ix_addon_artifacts_source_checksum", "addon_artifacts", ["source_checksum"])
    op.create_index("ix_addon_artifacts_params_hash", "addon_artifacts", ["params_hash"])


def downgrade() -> None:
    op.drop_index("ix_addon_artifacts_params_hash", table_name="addon_artifacts")
    op.drop_index("ix_addon_artifacts_source_checksum", table_name="addon_artifacts")
    op.drop_index("ix_addon_artifacts_status", table_name="addon_artifacts")
    op.drop_index("ix_addon_artifacts_asset_id", table_name="addon_artifacts")
    op.drop_index("ix_addon_artifacts_job_id", table_name="addon_artifacts")
    op.drop_index("ix_addon_artifacts_module_id", table_name="addon_artifacts")
    op.drop_table("addon_artifacts")

    op.drop_index("ix_addon_jobs_status", table_name="addon_jobs")
    op.drop_index("ix_addon_jobs_scope_type", table_name="addon_jobs")
    op.drop_index("ix_addon_jobs_created_by", table_name="addon_jobs")
    op.drop_index("ix_addon_jobs_module_id", table_name="addon_jobs")
    op.drop_table("addon_jobs")

    op.drop_index("ix_addon_presets_module_id", table_name="addon_presets")
    op.drop_table("addon_presets")
