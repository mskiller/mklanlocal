"""enable first-wave addons by default for existing installs

Revision ID: 0018_enable_first_wave_addons
Revises: 0017_addon_tools_foundation
Create Date: 2026-04-19 11:15:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_enable_first_wave_addons"
down_revision = "0017_addon_tools_foundation"
branch_labels = None
depends_on = None


FIRST_WAVE_ADDON_IDS = (
    "metadata_privacy",
    "export_recipes",
    "background_removal",
    "upscale_restore",
    "object_erase",
)


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE platform_modules
            SET enabled = true,
                updated_at = now()
            WHERE module_id IN :module_ids
            """
        ).bindparams(sa.bindparam("module_ids", expanding=True)),
        {"module_ids": FIRST_WAVE_ADDON_IDS},
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE platform_modules
            SET enabled = false,
                updated_at = now()
            WHERE module_id IN :module_ids
            """
        ).bindparams(sa.bindparam("module_ids", expanding=True)),
        {"module_ids": FIRST_WAVE_ADDON_IDS},
    )
