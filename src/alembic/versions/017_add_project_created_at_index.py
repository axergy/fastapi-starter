"""Add index on projects.created_at for pagination performance

Revision ID: 017
Revises: 016
Create Date: 2025-12-18 00:00:00.000000

Adds an index on the projects.created_at column to improve pagination
performance when listing projects by created_at DESC.
"""

from collections.abc import Sequence

from alembic import op
from src.alembic.migration_utils import is_tenant_migration

revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if not is_tenant_migration():
        return  # Skip for public migrations

    # Tenant schema - add index on created_at for pagination
    op.create_index("ix_projects_created_at", "projects", ["created_at"], unique=False)


def downgrade() -> None:
    if not is_tenant_migration():
        return

    op.drop_index("ix_projects_created_at", table_name="projects")
