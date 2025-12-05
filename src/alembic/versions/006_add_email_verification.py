"""Add email verification support

Revision ID: 006
Revises: 005
Create Date: 2025-12-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Skip if running tenant schema migrations (this is public schema only)
    if context.get_tag_argument():
        return

    # Add email verification columns to users table
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create email_verification_tokens table
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_verification_tokens_user_id",
        "email_verification_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_email_verification_tokens_token_hash",
        "email_verification_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    # Skip if running tenant schema migrations
    if context.get_tag_argument():
        return

    # Drop email_verification_tokens table
    op.drop_index("ix_email_verification_tokens_token_hash", "email_verification_tokens")
    op.drop_index("ix_email_verification_tokens_user_id", "email_verification_tokens")
    op.drop_table("email_verification_tokens")

    # Remove email verification columns from users table
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verified")
