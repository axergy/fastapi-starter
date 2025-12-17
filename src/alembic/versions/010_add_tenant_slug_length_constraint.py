"""Add tenant slug length constraint

Revision ID: 010
Revises: 009
Create Date: 2025-12-05 00:00:00.000000

Adds CHECK constraint to prevent tenant slugs that would result in
schema names exceeding PostgreSQL's 63-character identifier limit.

Max slug length = 63 - 7 (len("tenant_")) = 56 characters
"""

from collections.abc import Sequence

from alembic import op
from src.alembic.migration_utils import is_tenant_migration
from src.app.core.security.validators import MAX_TENANT_SLUG_LENGTH

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if is_tenant_migration():
        return

    # Add CHECK constraint for slug length to prevent schema name collisions
    # Two tenants with slugs differing only after char 56 would map to same schema
    op.create_check_constraint(
        "ck_tenants_slug_length",
        "tenants",
        f"length(slug) <= {MAX_TENANT_SLUG_LENGTH}",
    )

    # Also add CHECK constraint for valid slug format (lowercase alphanumeric + underscore)
    # Must match the regex in validators.py: ^[a-z][a-z0-9]*(_[a-z0-9]+)*$
    op.create_check_constraint(
        "ck_tenants_slug_format",
        "tenants",
        "slug ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'",
    )


def downgrade() -> None:
    if is_tenant_migration():
        return

    op.drop_constraint("ck_tenants_slug_format", "tenants", type_="check")
    op.drop_constraint("ck_tenants_slug_length", "tenants", type_="check")
