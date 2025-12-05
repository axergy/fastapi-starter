"""Tenant header extraction and validation dependencies."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import select

from src.app.core.db import get_public_session
from src.app.models import Tenant, TenantStatus


async def get_tenant_id_from_header(
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> str:
    """Extract tenant ID (slug) from header."""
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header is required",
        )
    return x_tenant_id


async def get_validated_tenant(
    tenant_slug: Annotated[str, Depends(get_tenant_id_from_header)],
) -> Tenant:
    """Validate tenant exists, is active, and is ready."""
    async with get_public_session() as session:
        result = await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        tenant = result.scalar_one_or_none()

        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
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
