"""Add assumed_by_user_id to audit_logs for identity assumption tracking

Revision ID: 012
Revises: 011
Create Date: 2025-12-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Skip if running tenant schema migrations (this is public schema only)
    if context.get_tag_argument():
        return

    # Add assumed_by_user_id column to track identity assumption
    # When a superuser assumes another user's identity, this field stores the superuser's ID
    op.add_column(
        "audit_logs",
        sa.Column("assumed_by_user_id", sa.Uuid(), nullable=True),
    )

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_audit_logs_assumed_by_user_id",
        "audit_logs",
        "users",
        ["assumed_by_user_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="SET NULL",
    )

    # Add index for efficient querying of assumed sessions
    op.create_index(
        "ix_audit_logs_assumed_by_user_id",
        "audit_logs",
        ["assumed_by_user_id"],
    )


def downgrade() -> None:
    # Skip if running tenant schema migrations
    if context.get_tag_argument():
        return

    # Drop index
    op.drop_index("ix_audit_logs_assumed_by_user_id", "audit_logs")

    # Drop foreign key constraint
    op.drop_constraint(
        "fk_audit_logs_assumed_by_user_id",
        "audit_logs",
        type_="foreignkey",
    )

    # Drop column
    op.drop_column("audit_logs", "assumed_by_user_id")
