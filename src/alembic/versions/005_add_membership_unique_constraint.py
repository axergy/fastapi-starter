"""Add unique constraint to user_tenant_membership

Revision ID: 005
Revises: 004
Create Date: 2025-12-04 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
from src.alembic.migration_utils import is_tenant_migration

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if is_tenant_migration():
        return

    op.create_unique_constraint(
        "uq_user_tenant_membership_user_tenant",
        "user_tenant_membership",
        ["user_id", "tenant_id"],
    )


def downgrade() -> None:
    if is_tenant_migration():
        return

    op.drop_constraint(
        "uq_user_tenant_membership_user_tenant",
        "user_tenant_membership",
        type_="unique",
    )
