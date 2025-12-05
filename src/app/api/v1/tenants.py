"""Tenant management endpoints."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from src.app.api.dependencies import AuthenticatedUser, TenantServiceDep
from src.app.models.public import TenantStatus
from src.app.schemas.pagination import PaginatedResponse
from src.app.schemas.tenant import (
    TenantCreate,
    TenantProvisioningResponse,
    TenantRead,
    TenantStatusResponse,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post(
    "",
    response_model=TenantProvisioningResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {
            "description": "Tenant provisioning started",
            "content": {
                "application/json": {
                    "example": {
                        "workflow_id": "tenant-provisioning-acme-corp",
                        "slug": "acme-corp",
                        "status": "provisioning",
                    }
                }
            },
        },
        409: {"description": "Tenant slug already exists"},
    },
)
async def create_tenant(
    request: TenantCreate,
    service: TenantServiceDep,
) -> TenantProvisioningResponse:
    """
    Start tenant provisioning workflow.

    Returns immediately with workflow ID. Poll /tenants/{slug}/status for progress.
    """
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


@router.get(
    "/{slug}/status",
    response_model=TenantStatusResponse,
    responses={
        200: {
            "description": "Tenant status retrieved",
            "content": {
                "application/json": {
                    "examples": {
                        "ready": {
                            "summary": "Tenant is ready",
                            "value": {
                                "status": "ready",
                                "tenant": {
                                    "id": "550e8400-e29b-41d4-a716-446655440000",
                                    "name": "Acme Corporation",
                                    "slug": "acme-corp",
                                    "status": "ready",
                                },
                            },
                        },
                        "provisioning": {
                            "summary": "Tenant is provisioning",
                            "value": {"status": "provisioning", "tenant": None},
                        },
                        "failed": {
                            "summary": "Provisioning failed",
                            "value": {"status": "failed", "tenant": None},
                        },
                    }
                }
            },
        },
        404: {"description": "Tenant not found"},
    },
)
async def get_tenant_status(slug: str, service: TenantServiceDep) -> TenantStatusResponse:
    """
    Check tenant provisioning status from database.

    Returns:
    - provisioning: Tenant is being provisioned
    - ready: Tenant is provisioned and ready to use
    - failed: Provisioning failed
    """
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


@router.get(
    "",
    response_model=PaginatedResponse[TenantRead],
    responses={
        200: {
            "description": "Paginated list of tenants",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                "name": "Acme Corporation",
                                "slug": "acme-corp",
                                "status": "ready",
                            },
                            {
                                "id": "6fa459ea-ee8a-3ca4-894e-db77e160355e",
                                "name": "Beta Industries",
                                "slug": "beta-industries",
                                "status": "ready",
                            },
                        ],
                        "next_cursor": "MjAyNC0wMS0yMFQxNDo0NTowMC4wMDAwMDA=",
                        "has_more": True,
                    }
                }
            },
        }
    },
)
async def list_tenants(
    current_user: AuthenticatedUser,
    service: TenantServiceDep,
    cursor: Annotated[str | None, Query(description="Cursor for pagination")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Number of items per page")] = 50,
) -> PaginatedResponse[TenantRead]:
    """List tenants where current user has membership.

    Uses cursor-based pagination for efficient traversal of large result sets.
    Pass the `next_cursor` from a response to get the next page.
    """
    # Get only tenants the user has access to
    tenants, next_cursor, has_more = await service.list_user_tenants(current_user.id, cursor, limit)
    return PaginatedResponse(
        items=[TenantRead.model_validate(t) for t in tenants],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get(
    "/{slug}",
    response_model=TenantRead,
    responses={
        200: {
            "description": "Tenant details",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Acme Corporation",
                        "slug": "acme-corp",
                        "status": "ready",
                    }
                }
            },
        },
        404: {"description": "Tenant not found"},
    },
)
async def get_tenant(slug: str, service: TenantServiceDep) -> TenantRead:
    """Get tenant by slug."""
    tenant = await service.get_by_slug(slug)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return TenantRead.model_validate(tenant)
