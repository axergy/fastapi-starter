"""Add refresh token expires_at indexes

Revision ID: 009
Revises: 008
Create Date: 2025-12-05 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import context, op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Skip if running tenant schema migrations (tag argument present)
    if context.get_tag_argument():
        return

    # Add index on expires_at for efficient cleanup queries
    # Used by background jobs that purge expired tokens
    op.create_index(
        "ix_refresh_tokens_expires_at",
        "refresh_tokens",
        ["expires_at"],
        unique=False,
    )

    # Add composite index on (tenant_id, expires_at)
    # Optimizes queries that check for valid tokens within a specific tenant
    # Common pattern: SELECT * FROM refresh_tokens WHERE tenant_id = ? AND expires_at > NOW()
    op.create_index(
        "ix_refresh_tokens_tenant_expires",
        "refresh_tokens",
        ["tenant_id", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    # Skip if running tenant schema migrations
    if context.get_tag_argument():
        return

    op.drop_index("ix_refresh_tokens_tenant_expires", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
