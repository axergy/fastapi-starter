"""Add tenant status field

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schema = context.get_tag_argument()

    if not schema:
        # Public schema only - add status column to tenants table
        op.add_column(
            "tenants",
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="ready",  # Existing tenants are ready
            ),
        )


def downgrade() -> None:
    schema = context.get_tag_argument()

    if not schema:
        op.drop_column("tenants", "status")
