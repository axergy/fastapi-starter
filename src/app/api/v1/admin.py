"""Admin API endpoints (superuser only)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.app.api.dependencies import AdminServiceDep, SuperUser, TenantServiceDep
from src.app.schemas.tenant import TenantRead

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/tenants",
    response_model=list[TenantRead],
    summary="List all tenants",
    description="List all tenants in the system. Requires superuser privileges.",
    responses={
        200: {
            "description": "List of all tenants",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "name": "Acme Corporation",
                            "slug": "acme-corp",
                            "status": "ready",
                            "is_active": True,
                            "created_at": "2024-01-15T10:30:00Z",
                        },
                        {
                            "id": "6fa459ea-ee8a-3ca4-894e-db77e160355e",
                            "name": "Beta Industries",
                            "slug": "beta-industries",
                            "status": "provisioning",
                            "is_active": True,
                            "created_at": "2024-01-20T14:45:00Z",
                        },
                    ]
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (superuser required)"},
    },
)
async def list_all_tenants(
    _user: SuperUser,
    tenant_service: TenantServiceDep,
) -> list[TenantRead]:
    """List all tenants (superuser only).

    Returns all tenants regardless of user membership.
    Includes both active and inactive tenants.
    """
    tenants = await tenant_service.list_tenants(active_only=False)
    return [TenantRead.model_validate(t) for t in tenants]


@router.delete(
    "/tenants/{tenant_id}",
    summary="Delete a tenant",
    description="Start tenant deletion workflow. Drops schema and soft-deletes record.",
    responses={
        200: {
            "description": "Deletion workflow started",
            "content": {
                "application/json": {
                    "example": {
                        "status": "deletion_started",
                        "workflow_id": "tenant-deletion-550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (superuser required)"},
        404: {"description": "Tenant not found or already deleted"},
    },
)
async def delete_tenant(
    tenant_id: UUID,
    _user: SuperUser,
    admin_service: AdminServiceDep,
) -> dict[str, str]:
    """Delete a tenant (superuser only).

    Starts an async workflow that:
    1. Drops the tenant's PostgreSQL schema (CASCADE)
    2. Soft-deletes the tenant record (sets deleted_at)
    """
    try:
        workflow_id = await admin_service.delete_tenant(tenant_id)
        return {"status": "deletion_started", "workflow_id": workflow_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.delete(
    "/tenants",
    summary="Bulk delete tenants",
    description="Delete multiple tenants by status filter. Useful for cleaning up failed tenants.",
    responses={
        200: {
            "description": "Deletion workflows started",
            "content": {
                "application/json": {
                    "example": {
                        "status": "deletion_started",
                        "count": 3,
                        "workflow_ids": [
                            "tenant-deletion-550e8400-e29b-41d4-a716-446655440000",
                            "tenant-deletion-6fa459ea-ee8a-3ca4-894e-db77e160355e",
                            "tenant-deletion-7cb349e0-f1ab-4bc5-995e-ec88f270466f",
                        ],
                    }
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (superuser required)"},
    },
)
async def bulk_delete_tenants(
    _user: SuperUser,
    admin_service: AdminServiceDep,
    status_filter: Annotated[
        str | None,
        Query(
            alias="status",
            description="Filter by tenant status (e.g., 'failed')",
            examples=["failed", "provisioning"],
        ),
    ] = None,
) -> dict[str, str | int | list[str]]:
    """Bulk delete tenants by status (superuser only).

    Starts deletion workflows for all tenants matching the filter.
    If no filter is provided, deletes ALL non-deleted tenants (use with caution!).
    """
    workflow_ids = await admin_service.bulk_delete_tenants(status_filter)
    return {
        "status": "deletion_started",
        "count": len(workflow_ids),
        "workflow_ids": workflow_ids,
    }
