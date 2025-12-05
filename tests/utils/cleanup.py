"""Database cleanup utilities for test fixtures.

These utilities handle proper FK-constraint-aware cleanup of test data.
The delete order matters due to foreign key relationships.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


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
    """Drop tenant schema.

    Note: schema_name should already be validated before calling this function.
    This uses string formatting because schema names cannot be parameterized in SQL.
    """
    await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
