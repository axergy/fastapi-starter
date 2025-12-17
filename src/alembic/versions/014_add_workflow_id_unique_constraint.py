"""Add unique constraint to workflow_id

Revision ID: 014
Revises: 013
Create Date: 2025-12-16 00:00:00.000000

Adds a unique constraint to workflow_executions.workflow_id to ensure
only one workflow execution per workflow_id can exist. The unique constraint
replaces the non-unique index and implicitly creates a unique index.
"""

from collections.abc import Sequence

from alembic import op
from src.alembic.migration_utils import is_tenant_migration

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if is_tenant_migration():
        return

    # Drop existing non-unique index
    op.drop_index("ix_workflow_executions_workflow_id", "workflow_executions")
    # Create unique constraint (implicitly creates unique index)
    op.create_unique_constraint(
        "uq_workflow_executions_workflow_id",
        "workflow_executions",
        ["workflow_id"],
        schema="public",
    )


def downgrade() -> None:
    if is_tenant_migration():
        return

    # Drop unique constraint
    op.drop_constraint("uq_workflow_executions_workflow_id", "workflow_executions", schema="public")
    # Recreate non-unique index
    op.create_index("ix_workflow_executions_workflow_id", "workflow_executions", ["workflow_id"])
