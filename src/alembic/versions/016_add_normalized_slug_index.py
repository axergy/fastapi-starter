"""Add unique index on normalized slug to prevent race conditions

Revision ID: 016
Revises: 015
Create Date: 2025-12-18 00:00:00.000000

Adds a functional unique index on the normalized slug (with hyphens replaced
by underscores) to prevent race conditions where "acme-corp" and "acme_corp"
could both be created, mapping to the same tenant schema.
"""

from collections.abc import Sequence

from alembic import op
from src.alembic.migration_utils import is_tenant_migration

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if is_tenant_migration():
        return

    # Create unique index on normalized slug to prevent race conditions
    # This prevents "acme-corp" and "acme_corp" from both existing
    op.execute(
        """
        CREATE UNIQUE INDEX idx_tenants_slug_normalized
        ON public.tenants (REPLACE(slug, '-', '_'))
        """
    )


def downgrade() -> None:
    if is_tenant_migration():
        return

    op.drop_index("idx_tenants_slug_normalized", table_name="tenants", schema="public")
