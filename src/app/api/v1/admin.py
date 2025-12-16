"""Admin API endpoints (superuser only)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.app.api.dependencies import (
    AdminServiceDep,
    AssumeIdentityServiceDep,
    AuditLogRepo,
    DBSession,
    SuperUser,
    TenantServiceDep,
)
from src.app.models.public import AuditAction
from src.app.schemas.assume_identity import AssumeIdentityRequest, AssumeIdentityResponse
from src.app.schemas.pagination import PaginatedResponse
from src.app.schemas.tenant import TenantRead
from src.app.services.audit_service import AuditService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/tenants",
    response_model=PaginatedResponse[TenantRead],
    summary="List all tenants",
    description="List all tenants in the system with pagination. Requires superuser privileges.",
    responses={
        200: {
            "description": "Paginated list of all tenants",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
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
                        ],
                        "next_cursor": "MjAyNC0wMS0yMFQxNDo0NTowMC4wMDAwMDA=",
                        "has_more": False,
                    }
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
    cursor: Annotated[str | None, Query(description="Cursor for pagination")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Number of items per page")] = 50,
) -> PaginatedResponse[TenantRead]:
    """List all tenants (superuser only).

    Returns all tenants regardless of user membership.
    Includes both active and inactive tenants.
    Uses cursor-based pagination for efficient traversal.
    """
    tenants, next_cursor, has_more = await tenant_service.list_tenants(
        cursor, limit, active_only=False
    )
    return PaginatedResponse(
        items=[TenantRead.model_validate(t) for t in tenants],
        next_cursor=next_cursor,
        has_more=has_more,
    )


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


@router.post(
    "/assume-identity",
    response_model=AssumeIdentityResponse,
    summary="Assume user identity",
    description=(
        "Start an assumed identity session as a target user in a specific tenant. "
        "Returns a time-limited JWT token (15 minutes) that allows the superuser to "
        "act as the target user. All actions performed with this token are audited "
        "with both the actual operator and the assumed user identities."
    ),
    responses={
        200: {
            "description": "Assumed identity session started",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer",
                        "expires_in": 900,
                        "assumed_user_id": "550e8400-e29b-41d4-a716-446655440000",
                        "assumed_user_email": "user@example.com",
                        "tenant_id": "660e8400-e29b-41d4-a716-446655440000",
                        "tenant_slug": "acme-corp",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "examples": {
                        "user_not_found": {"value": {"detail": "Target user not found"}},
                        "user_inactive": {"value": {"detail": "Target user is inactive"}},
                        "user_is_superuser": {
                            "value": {"detail": "Cannot assume identity of another superuser"}
                        },
                        "tenant_not_found": {"value": {"detail": "Tenant not found"}},
                        "no_membership": {
                            "value": {"detail": "Target user does not have access to this tenant"}
                        },
                    }
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (superuser required)"},
    },
)
async def assume_identity(
    request: AssumeIdentityRequest,
    superuser: SuperUser,
    assume_identity_service: AssumeIdentityServiceDep,
    audit_repo: AuditLogRepo,
    session: DBSession,
) -> AssumeIdentityResponse:
    """Assume a user's identity (superuser only).

    Creates a time-limited access token that allows the superuser to act as the
    target user in the specified tenant. The token has a shorter expiry (15 minutes)
    than regular access tokens for security.

    Security restrictions:
    - Only superusers can assume identities
    - Cannot assume the identity of another superuser
    - Target user must have active membership in the specified tenant

    Audit logging:
    - The assumption start is logged with IDENTITY_ASSUMED action
    - All actions performed with the assumed token include both user IDs in audit logs
    """
    try:
        response = await assume_identity_service.assume_identity(
            operator=superuser,
            target_user_id=request.target_user_id,
            tenant_id=request.tenant_id,
            reason=request.reason,
        )

        # Log the assumption start
        audit_service = AuditService(audit_repo, session, request.tenant_id)
        await audit_service.log_action(
            action=AuditAction.IDENTITY_ASSUMED,
            entity_type="user",
            entity_id=request.target_user_id,
            user_id=superuser.id,
            changes={
                "assumed_user_id": str(request.target_user_id),
                "tenant_id": str(request.tenant_id),
                "reason": request.reason,
                "expires_in_seconds": response.expires_in,
            },
        )

        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
