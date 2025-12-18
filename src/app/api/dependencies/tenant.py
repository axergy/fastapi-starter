"""Tenant header extraction and validation dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.app.core.db import get_session
from src.app.models import Tenant, TenantStatus


async def _get_session_for_tenant_validation() -> AsyncGenerator[AsyncSession]:
    """Get session for tenant validation (breaks circular import)."""
    async with get_session() as session:
        yield session


async def get_tenant_slug_from_header(
    x_tenant_slug: Annotated[str | None, Header()] = None,
) -> str:
    """Extract tenant slug from header."""
    if not x_tenant_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-Slug header is required",
        )
    return x_tenant_slug


async def get_validated_tenant(
    tenant_slug: Annotated[str, Depends(get_tenant_slug_from_header)],
    session: Annotated[AsyncSession, Depends(_get_session_for_tenant_validation)],
) -> Tenant:
    """Validate tenant exists, is active, and is ready."""
    result = await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
    tenant = result.scalar_one_or_none()

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    if tenant.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Tenant has been deleted",
        )

    if not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant is inactive",
        )

    if tenant.status != TenantStatus.READY.value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Tenant is {tenant.status}",
        )

    return tenant


ValidatedTenant = Annotated[Tenant, Depends(get_validated_tenant)]
