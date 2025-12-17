"""Add tenant invites table

Revision ID: 007
Revises: 006
Create Date: 2025-12-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from src.alembic.migration_utils import is_tenant_migration

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if is_tenant_migration():
        return

    # Create tenant_invites table
    op.create_table(
        "tenant_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="member"),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("accepted_by_user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["public.users.id"]),
        sa.ForeignKeyConstraint(["accepted_by_user_id"], ["public.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )

    # Create indexes
    op.create_index(
        "ix_tenant_invites_tenant_id",
        "tenant_invites",
        ["tenant_id"],
        schema="public",
    )
    op.create_index(
        "ix_tenant_invites_email",
        "tenant_invites",
        ["email"],
        schema="public",
    )
    op.create_index(
        "ix_tenant_invites_token_hash",
        "tenant_invites",
        ["token_hash"],
        unique=True,
        schema="public",
    )
    op.create_index(
        "ix_tenant_invites_invited_by_user_id",
        "tenant_invites",
        ["invited_by_user_id"],
        schema="public",
    )
    # Composite index for looking up pending invites by email and tenant
    op.create_index(
        "ix_tenant_invites_email_tenant_status",
        "tenant_invites",
        ["email", "tenant_id", "status"],
        schema="public",
    )


def downgrade() -> None:
    if is_tenant_migration():
        return

    # Drop indexes
    op.drop_index(
        "ix_tenant_invites_email_tenant_status", table_name="tenant_invites", schema="public"
    )
    op.drop_index(
        "ix_tenant_invites_invited_by_user_id", table_name="tenant_invites", schema="public"
    )
    op.drop_index("ix_tenant_invites_token_hash", table_name="tenant_invites", schema="public")
    op.drop_index("ix_tenant_invites_email", table_name="tenant_invites", schema="public")
    op.drop_index("ix_tenant_invites_tenant_id", table_name="tenant_invites", schema="public")

    # Drop table
    op.drop_table("tenant_invites", schema="public")
