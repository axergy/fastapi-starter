"""User management endpoints."""

from fastapi import APIRouter

from src.app.api.dependencies import (
    AuthenticatedUser,
    CurrentUser,
    TenantServiceDep,
    UserServiceDep,
)
from src.app.schemas.tenant import TenantRead
from src.app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_current_user(current_user: CurrentUser) -> UserRead:
    """Get current authenticated user."""
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead)
async def update_current_user(
    data: UserUpdate,
    current_user: CurrentUser,
    service: UserServiceDep,
) -> UserRead:
    """Update current user."""
    updated_user = await service.update(current_user, data)
    return UserRead.model_validate(updated_user)


@router.get(
    "/me/tenants",
    response_model=list[TenantRead],
    responses={
        200: {
            "description": "List of tenants the user belongs to",
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
                            "status": "ready",
                            "is_active": True,
                            "created_at": "2024-02-20T14:45:00Z",
                        },
                    ]
                }
            },
        }
    },
)
async def list_my_tenants(
    current_user: AuthenticatedUser,
    tenant_service: TenantServiceDep,
) -> list[TenantRead]:
    """List all tenants the current user belongs to.

    This endpoint does not require a tenant context (X-Tenant-ID header),
    making it useful for tenant selection screens after login.
    """
    tenants = await tenant_service.list_user_tenants(current_user.id)
    return [TenantRead.model_validate(t) for t in tenants]
