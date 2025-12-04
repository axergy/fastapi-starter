"""Add unique constraint to user_tenant_membership

Revision ID: 005
Revises: 004
Create Date: 2025-12-04 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import context, op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Skip if running tenant schema migrations (this is public schema only)
    if context.get_tag_argument():
        return

    op.create_unique_constraint(
        "uq_user_tenant_membership_user_tenant",
        "user_tenant_membership",
        ["user_id", "tenant_id"],
    )


def downgrade() -> None:
    # Skip if running tenant schema migrations
    if context.get_tag_argument():
        return

    op.drop_constraint(
        "uq_user_tenant_membership_user_tenant",
        "user_tenant_membership",
        type_="unique",
    )
