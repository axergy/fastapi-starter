"""Database cleanup utilities for test fixtures.

These utilities handle proper FK-constraint-aware cleanup of test data.
The delete order matters due to foreign key relationships.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from src.app.core.security.validators import validate_schema_name


def _validate_schema_name_for_drop(schema_name: str) -> None:
    """Validate schema name before using in DROP SCHEMA statement.

    This prevents SQL injection by ensuring schema_name matches the strict
    tenant naming convention before interpolating into SQL.

    Args:
        schema_name: The schema name to validate

    Raises:
        ValueError: If schema name doesn't match expected tenant format
    """
    validate_schema_name(schema_name)


async def cleanup_tenant_cascade(conn: AsyncConnection, tenant_id: UUID) -> None:
    """Delete tenant and all related data in correct FK order.

    Order: invites -> memberships -> tokens -> tenant
    """
    await conn.execute(
        text("DELETE FROM public.tenant_invites WHERE tenant_id = :id"),
        {"id": tenant_id},
    )
    await conn.execute(
        text("DELETE FROM public.user_tenant_membership WHERE tenant_id = :id"),
        {"id": tenant_id},
    )
    await conn.execute(
        text("DELETE FROM public.refresh_tokens WHERE tenant_id = :id"),
        {"id": tenant_id},
    )
    await conn.execute(
        text("DELETE FROM public.tenants WHERE id = :id"),
        {"id": tenant_id},
    )


async def cleanup_user_cascade(conn: AsyncConnection, user_id: UUID) -> None:
    """Delete user and all related data in correct FK order.

    Order: invites (by inviter) -> memberships -> user
    """
    await conn.execute(
        text("DELETE FROM public.tenant_invites WHERE invited_by_user_id = :id"),
        {"id": user_id},
    )
    await conn.execute(
        text("DELETE FROM public.tenant_invites WHERE accepted_by_user_id = :id"),
        {"id": user_id},
    )
    await conn.execute(
        text("DELETE FROM public.user_tenant_membership WHERE user_id = :id"),
        {"id": user_id},
    )
    await conn.execute(
        text("DELETE FROM public.users WHERE id = :id"),
        {"id": user_id},
    )


async def drop_tenant_schema(conn: AsyncConnection, schema_name: str) -> None:
    """Drop tenant schema with SQL injection protection.

    Validates schema_name matches strict tenant naming convention before
    executing DROP SCHEMA. Schema names cannot be parameterized in SQL,
    so validation is critical to prevent injection attacks.

    Args:
        conn: Async database connection
        schema_name: Must match pattern 'tenant_<slug>' (e.g., 'tenant_acme')

    Raises:
        ValueError: If schema_name doesn't match expected tenant format
    """
    _validate_schema_name_for_drop(schema_name)
    # Safe to interpolate after validation - pattern only allows [a-z0-9_]
    await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
