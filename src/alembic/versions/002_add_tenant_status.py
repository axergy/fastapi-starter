"""Add tenant status field

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

NOTE: This migration is now idempotent since status column is included in 001_initial.py.
For existing databases that already ran 001 without the status column, this will add it.
For fresh installs where 001 already includes the column, this is a no-op.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def column_exists(table_name: str, column_name: str, schema: str = "public") -> bool:
    """Check if a column exists in a table within a specific schema."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = :table_schema
                  AND table_name = :table_name
                  AND column_name = :column_name
            )
            """
        ),
        {"table_schema": schema, "table_name": table_name, "column_name": column_name},
    )
    return result.scalar()


def upgrade() -> None:
    schema = context.get_tag_argument()

    # Only add column if it doesn't exist (idempotent for public schema)
    if not schema and not column_exists("tenants", "status"):
        op.add_column(
            "tenants",
            sa.Column(
                "status",
                sa.String(50),
                nullable=False,
                server_default="ready",  # Existing tenants are ready
            ),
        )


def downgrade() -> None:
    schema = context.get_tag_argument()

    if not schema and column_exists("tenants", "status"):
        op.drop_column("tenants", "status")
