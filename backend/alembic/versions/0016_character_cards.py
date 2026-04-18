"""character cards module

Revision ID: 0016_character_cards
Revises: 0015_platform_modules
Create Date: 2026-04-18 06:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0016_character_cards"
down_revision = "0015_platform_modules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "character_cards",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("creator", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("spec", sa.String(length=64), nullable=False, server_default="chara_card_v3"),
        sa.Column("spec_version", sa.String(length=32), nullable=False, server_default="3.0"),
        sa.Column("tags_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("card_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_character_cards_name", "character_cards", ["name"])
    op.create_index("ix_character_cards_creator", "character_cards", ["creator"])


def downgrade() -> None:
    op.drop_index("ix_character_cards_creator", table_name="character_cards")
    op.drop_index("ix_character_cards_name", table_name="character_cards")
    op.drop_table("character_cards")
