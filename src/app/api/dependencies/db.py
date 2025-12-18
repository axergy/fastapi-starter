"""Database session dependencies - Lobby Pattern."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.api.dependencies.tenant import ValidatedTenant
from src.app.core.db import get_public_session, get_tenant_session


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Get database session for public schema (Lobby Pattern)."""
    async with get_public_session() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db_session)]

# Alias for clarity
PublicDBSession = DBSession


async def get_tenant_db_session(
    tenant: ValidatedTenant,
) -> AsyncGenerator[AsyncSession]:
    """Get database session scoped to validated tenant schema.

    Combines tenant validation (from X-Tenant-Slug header) with
    schema-isolated session for tenant-specific data access.
    """
    async with get_tenant_session(tenant.schema_name) as session:
        yield session


TenantDBSession = Annotated[AsyncSession, Depends(get_tenant_db_session)]
