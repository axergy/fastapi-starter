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
