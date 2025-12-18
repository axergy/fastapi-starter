"""Tenant validation dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.app.core.db import get_session
from src.app.models import Tenant, TenantStatus


async def _session() -> AsyncGenerator[AsyncSession]:
    async with get_session() as session:
        yield session


async def _validate(slug: str, session: AsyncSession) -> Tenant:
    result = await session.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if tenant.deleted_at:
        raise HTTPException(status.HTTP_410_GONE, detail="Tenant has been deleted")
    if not tenant.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Tenant is inactive")
    if tenant.status != TenantStatus.READY.value:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Tenant is {tenant.status}"
        )
    return tenant


async def get_tenant(
    x_tenant_slug: Annotated[str | None, Header()] = None,
    session: Annotated[AsyncSession, Depends(_session)] = None,  # type: ignore[assignment]
) -> Tenant | None:
    """Resolve tenant from X-Tenant-Slug header (optional)."""
    return await _validate(x_tenant_slug, session) if x_tenant_slug else None


def require_tenant(tenant: Annotated[Tenant | None, Depends(get_tenant)]) -> Tenant:
    """Enforce tenant is present, raise 400 if missing."""
    if not tenant:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="X-Tenant-Slug header is required")
    return tenant


ValidatedTenant = Annotated[Tenant, Depends(require_tenant)]
