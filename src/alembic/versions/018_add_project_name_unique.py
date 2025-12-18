"""Add unique constraint on projects.name

Revision ID: 018
Revises: 017
Create Date: 2025-12-18 00:00:00.000000

Adds a unique constraint on the projects.name column to prevent duplicate
project names within a tenant schema.
"""

from collections.abc import Sequence

from alembic import op
from src.alembic.migration_utils import is_tenant_migration

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if not is_tenant_migration():
        return  # Only applies to tenant schemas

    # Drop the existing non-unique index
    op.drop_index("ix_projects_name", table_name="projects")

    # Create a unique constraint on the name column
    op.create_unique_constraint("uq_projects_name", "projects", ["name"])


def downgrade() -> None:
    if not is_tenant_migration():
        return

    # Remove the unique constraint
    op.drop_constraint("uq_projects_name", "projects", type_="unique")

    # Recreate the non-unique index
    op.create_index("ix_projects_name", "projects", ["name"], unique=False)
