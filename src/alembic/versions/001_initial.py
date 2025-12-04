"""Initial migration

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import context, op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Check if we're running in a tenant schema (tag provided) or public
    schema = context.get_tag_argument()

    if schema:
        # Tenant schema - create users and refresh_tokens tables
        # search_path is already set by env.py, so no schema= needed
        op.create_table(
            "users",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("email", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
            sa.Column(
                "hashed_password", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
            ),
            sa.Column("full_name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)

        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column(
                "token_hash", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
            ),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)
        op.create_index(
            "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
        )
    else:
        # Public schema - create tenants table
        op.create_table(
            "tenants",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
            sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_tenants_name", "tenants", ["name"], unique=False)
        op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)


def downgrade() -> None:
    schema = context.get_tag_argument()

    if schema:
        op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
        op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
        op.drop_table("refresh_tokens")
        op.drop_index("ix_users_email", table_name="users")
        op.drop_table("users")
    else:
        op.drop_index("ix_tenants_slug", table_name="tenants")
        op.drop_index("ix_tenants_name", table_name="tenants")
        op.drop_table("tenants")
