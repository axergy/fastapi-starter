"""Add audit_logs table

Revision ID: 011
Revises: 010
Create Date: 2025-12-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op
from src.alembic.migration_utils import is_tenant_migration

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if is_tenant_migration():
        return

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("changes", JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["public.tenants.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["public.users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for efficient querying
    op.create_index(
        "ix_audit_logs_tenant_id",
        "audit_logs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_audit_logs_user_id",
        "audit_logs",
        ["user_id"],
    )
    # Composite indexes for common query patterns
    op.create_index(
        "ix_audit_logs_tenant_created",
        "audit_logs",
        ["tenant_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_audit_logs_user_created",
        "audit_logs",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_audit_logs_action_created",
        "audit_logs",
        ["action", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_audit_logs_entity",
        "audit_logs",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    if is_tenant_migration():
        return

    # Drop indexes
    op.drop_index("ix_audit_logs_entity", "audit_logs")
    op.drop_index("ix_audit_logs_action_created", "audit_logs")
    op.drop_index("ix_audit_logs_user_created", "audit_logs")
    op.drop_index("ix_audit_logs_tenant_created", "audit_logs")
    op.drop_index("ix_audit_logs_user_id", "audit_logs")
    op.drop_index("ix_audit_logs_tenant_id", "audit_logs")

    # Drop table
    op.drop_table("audit_logs")
