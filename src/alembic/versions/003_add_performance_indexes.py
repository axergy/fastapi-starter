"""Add performance indexes

Revision ID: 003
Revises: 001
Create Date: 2025-12-04 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
from src.alembic.migration_utils import is_tenant_migration

revision: str = "003"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if is_tenant_migration():
        return

    # For refresh_tokens - improves token refresh queries
    # When users refresh their tokens, we query by both user_id and tenant_id
    op.create_index(
        "ix_refresh_tokens_user_tenant",
        "refresh_tokens",
        ["user_id", "tenant_id"],
        unique=False,
    )

    # For membership lookups - critical for auth performance
    # Most auth checks need to verify user + tenant + active status
    op.create_index(
        "ix_membership_user_tenant_active",
        "user_tenant_membership",
        ["user_id", "tenant_id", "is_active"],
        unique=False,
    )

    # For listing tenant's users
    # When displaying users for a tenant, we filter by tenant_id and is_active
    op.create_index(
        "ix_membership_tenant_active",
        "user_tenant_membership",
        ["tenant_id", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    if is_tenant_migration():
        return

    op.drop_index("ix_refresh_tokens_user_tenant", table_name="refresh_tokens")
    op.drop_index("ix_membership_user_tenant_active", table_name="user_tenant_membership")
    op.drop_index("ix_membership_tenant_active", table_name="user_tenant_membership")
