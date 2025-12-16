"""Fix slug column length to match code (56 chars)

Revision ID: 013
Revises: 012
Create Date: 2025-12-16 00:00:00.000000

Increases the slug column length from 50 to 56 characters to match
the MAX_SLUG_LENGTH constant in code and the CHECK constraint added
in migration 010.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Skip if running tenant schema migrations (this is public schema only)
    if context.get_tag_argument():
        return

    # Alter column to increase length from 50 to 56 characters
    op.alter_column(
        "tenants",
        "slug",
        type_=sa.String(56),
        existing_type=sa.String(50),
        schema="public",
    )


def downgrade() -> None:
    # Skip if running tenant schema migrations
    if context.get_tag_argument():
        return

    # WARNING: This will fail if any slugs > 50 characters exist in the database
    # You will need to manually truncate or modify any such slugs before downgrading
    op.alter_column(
        "tenants",
        "slug",
        type_=sa.String(50),
        existing_type=sa.String(56),
        schema="public",
    )
