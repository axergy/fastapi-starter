"""Add projects table for tenant schemas

Revision ID: 015
Revises: 014
Create Date: 2024-12-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op
from src.alembic.migration_utils import is_tenant_migration

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if not is_tenant_migration():
        return  # Skip for public migrations

    # Tenant schema - create projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_name", "projects", ["name"], unique=False)


def downgrade() -> None:
    if not is_tenant_migration():
        return

    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_table("projects")
