"""Add email verification support

Revision ID: 006
Revises: 005
Create Date: 2025-12-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from src.alembic.migration_utils import is_tenant_migration

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if is_tenant_migration():
        return

    # Add email verification columns to users table
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        schema="public",
    )
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(), nullable=True),
        schema="public",
    )

    # Create email_verification_tokens table
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )
    op.create_index(
        "ix_email_verification_tokens_user_id",
        "email_verification_tokens",
        ["user_id"],
        schema="public",
    )
    op.create_index(
        "ix_email_verification_tokens_token_hash",
        "email_verification_tokens",
        ["token_hash"],
        unique=True,
        schema="public",
    )


def downgrade() -> None:
    if is_tenant_migration():
        return

    # Drop email_verification_tokens table
    op.drop_index(
        "ix_email_verification_tokens_token_hash",
        table_name="email_verification_tokens",
        schema="public",
    )
    op.drop_index(
        "ix_email_verification_tokens_user_id",
        table_name="email_verification_tokens",
        schema="public",
    )
    op.drop_table("email_verification_tokens", schema="public")

    # Remove email verification columns from users table
    op.drop_column("users", "email_verified_at", schema="public")
    op.drop_column("users", "email_verified", schema="public")
