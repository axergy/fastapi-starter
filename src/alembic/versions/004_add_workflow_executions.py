"""Add workflow_executions table

Revision ID: 004
Revises: 003
Create Date: 2025-12-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # This table is for public schema only
    # Skip if running tenant schema migrations (tag argument present)
    if context.get_tag_argument():
        return

    op.create_table(
        "workflow_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", sa.String(length=255), nullable=False),
        sa.Column("workflow_type", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )
    op.create_index(
        "ix_workflow_executions_workflow_id",
        "workflow_executions",
        ["workflow_id"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_workflow_executions_entity_id",
        "workflow_executions",
        ["entity_id"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    # Skip if running tenant schema migrations
    if context.get_tag_argument():
        return

    op.drop_index(
        "ix_workflow_executions_entity_id", table_name="workflow_executions", schema="public"
    )
    op.drop_index(
        "ix_workflow_executions_workflow_id", table_name="workflow_executions", schema="public"
    )
    op.drop_table("workflow_executions", schema="public")
