"""Tenant management endpoints."""

from fastapi import APIRouter, HTTPException, status

from src.app.core.db import get_public_session
from src.app.models.public import TenantStatus
from src.app.repositories.tenant_repository import TenantRepository
from src.app.schemas.tenant import (
    TenantCreate,
    TenantProvisioningResponse,
    TenantRead,
    TenantStatusResponse,
)
from src.app.services.tenant_service import TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantProvisioningResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_tenant(request: TenantCreate) -> TenantProvisioningResponse:
    """
    Start tenant provisioning workflow.

    Returns immediately with workflow ID. Poll /tenants/{slug}/status for progress.
    """
    async with get_public_session() as session:
        tenant_repo = TenantRepository(session)
        service = TenantService(tenant_repo)
        try:
            workflow_id = await service.create_tenant(request.name, request.slug)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from e

    return TenantProvisioningResponse(
        workflow_id=workflow_id,
        slug=request.slug,
        status="provisioning",
    )


@router.get("/{slug}/status", response_model=TenantStatusResponse)
async def get_tenant_status(slug: str) -> TenantStatusResponse:
    """
    Check tenant provisioning status from database.

    Returns:
    - provisioning: Tenant is being provisioned
    - ready: Tenant is provisioned and ready to use
    - failed: Provisioning failed
    """
    async with get_public_session() as session:
        tenant_repo = TenantRepository(session)
        service = TenantService(tenant_repo)
        tenant = await service.get_by_slug(slug)

        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{slug}' not found",
            )

        is_ready = tenant.status == TenantStatus.READY.value
        tenant_read = TenantRead.model_validate(tenant) if is_ready else None
        return TenantStatusResponse(
            status=tenant.status,
            tenant=tenant_read,
        )


@router.get("", response_model=list[TenantRead])
async def list_tenants() -> list[TenantRead]:
    """List all active tenants."""
    async with get_public_session() as session:
        tenant_repo = TenantRepository(session)
        service = TenantService(tenant_repo)
        tenants = await service.list_tenants()
        return [TenantRead.model_validate(t) for t in tenants]


@router.get("/{slug}", response_model=TenantRead)
async def get_tenant(slug: str) -> TenantRead:
    """Get tenant by slug."""
    async with get_public_session() as session:
        tenant_repo = TenantRepository(session)
        service = TenantService(tenant_repo)
        tenant = await service.get_by_slug(slug)
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )
        return TenantRead.model_validate(tenant)
