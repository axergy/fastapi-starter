"""Admin API endpoints (superuser only)."""

from fastapi import APIRouter

from src.app.api.dependencies import SuperUser, TenantServiceDep
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
