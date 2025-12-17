"""Add unique constraint to user_tenant_membership

Revision ID: 005
Revises: 004
Create Date: 2025-12-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from src.alembic.migration_utils import is_tenant_migration

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _constraint_exists(constraint_name: str) -> bool:
    """Check if a constraint exists in the public schema."""
    bind = op.get_bind()
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_namespace n ON n.oid = c.connamespace
                    WHERE n.nspname = 'public'
                      AND c.conname = :name
                )
                """
            ),
            {"name": constraint_name},
        ).scalar()
    )


def upgrade() -> None:
    if is_tenant_migration():
        return

    # If the table already has a composite PK, uniqueness is already guaranteed.
    if _constraint_exists("user_tenant_membership_pkey"):
        return

    # If the unique constraint already exists, do nothing (idempotent).
    if _constraint_exists("uq_user_tenant_membership_user_tenant"):
        return

    op.create_unique_constraint(
        "uq_user_tenant_membership_user_tenant",
        "user_tenant_membership",
        ["user_id", "tenant_id"],
        schema="public",
    )


def downgrade() -> None:
    if is_tenant_migration():
        return

    if not _constraint_exists("uq_user_tenant_membership_user_tenant"):
        return

    op.drop_constraint(
        "uq_user_tenant_membership_user_tenant",
        "user_tenant_membership",
        schema="public",
        type_="unique",
    )
