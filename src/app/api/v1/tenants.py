from fastapi import APIRouter, HTTPException, status

from src.app.core.db import get_public_session
from src.app.schemas.tenant import TenantCreate, TenantRead
from src.app.services.tenant_service import TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
async def create_tenant(request: TenantCreate) -> TenantRead:
    """
    Create a new tenant.

    This creates a tenant record and provisions a new database schema.
    """
    async with get_public_session() as session:
        service = TenantService(session)
        try:
            tenant = await service.create_tenant(name=request.name, slug=request.slug)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from None
        return TenantRead.model_validate(tenant)


@router.get("", response_model=list[TenantRead])
async def list_tenants() -> list[TenantRead]:
    """List all active tenants."""
    async with get_public_session() as session:
        service = TenantService(session)
        tenants = await service.list_tenants()
        return [TenantRead.model_validate(t) for t in tenants]


@router.get("/{slug}", response_model=TenantRead)
async def get_tenant(slug: str) -> TenantRead:
    """Get tenant by slug."""
    async with get_public_session() as session:
        service = TenantService(session)
        tenant = await service.get_by_slug(slug)
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )
        return TenantRead.model_validate(tenant)
