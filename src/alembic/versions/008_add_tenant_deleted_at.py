"""Add deleted_at column to tenants table

Revision ID: 008
Revises: 007
Create Date: 2025-12-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Skip if running tenant schema migrations (this is public schema only)
    if context.get_tag_argument():
        return

    # Add deleted_at column (nullable, null means not deleted)
    op.add_column(
        "tenants",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add partial index for efficient cleanup queries (only indexes non-null values)
    op.create_index(
        "ix_tenants_deleted_at",
        "tenants",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )

    # Add partial index for finding failed tenants for cleanup
    op.create_index(
        "ix_tenants_status_created_at_failed",
        "tenants",
        ["status", "created_at"],
        postgresql_where=sa.text("status = 'failed' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    # Skip if running tenant schema migrations
    if context.get_tag_argument():
        return

    op.drop_index("ix_tenants_status_created_at_failed", "tenants")
    op.drop_index("ix_tenants_deleted_at", "tenants")
    op.drop_column("tenants", "deleted_at")
