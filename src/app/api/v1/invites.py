"""Tenant invite API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from src.app.api.dependencies import (
    AdminUser,
    InviteServiceDep,
    InviteServicePublicDep,
)
from src.app.core.rate_limit import limiter
from src.app.schemas.invite import (
    AcceptInviteRequest,
    AcceptInviteResponse,
    InviteCancelResponse,
    InviteCreateRequest,
    InviteCreateResponse,
    InviteInfoResponse,
    InviteRead,
)
from src.app.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/invites", tags=["invites"])


# =============================================================================
# Admin Endpoints (require X-Tenant-ID header + admin role)
# =============================================================================


@router.post(
    "",
    response_model=InviteCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create invite",
    description="Create and send an invite to join the tenant. Admin role required.",
    responses={
        201: {
            "description": "Invite created and sent",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "newuser@example.com",
                        "role": "member",
                        "expires_at": "2024-01-22T10:30:00Z",
                        "message": "Invite sent successfully",
                    }
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin role required)"},
        409: {"description": "User already member or invite already pending"},
    },
)
async def create_invite(
    request: InviteCreateRequest,
    admin_user: AdminUser,
    invite_service: InviteServiceDep,
) -> InviteCreateResponse:
    """Create and send an invite."""
    try:
        invite, _ = await invite_service.create_invite(
            email=request.email,
            invited_by_user_id=admin_user.id,
            role=request.role,
        )
        return InviteCreateResponse(
            id=invite.id,
            email=invite.email,
            role=invite.role,
            expires_at=invite.expires_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.get(
    "",
    response_model=PaginatedResponse[InviteRead],
    summary="List pending invites",
    description="List all pending invites for the tenant with pagination. Admin role required.",
    responses={
        200: {
            "description": "Paginated list of pending invites",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                "email": "user1@example.com",
                                "role": "member",
                                "status": "pending",
                                "expires_at": "2024-01-22T10:30:00Z",
                                "created_at": "2024-01-15T10:30:00Z",
                            },
                            {
                                "id": "6fa459ea-ee8a-3ca4-894e-db77e160355e",
                                "email": "user2@example.com",
                                "role": "admin",
                                "status": "pending",
                                "expires_at": "2024-01-23T14:45:00Z",
                                "created_at": "2024-01-16T14:45:00Z",
                            },
                        ],
                        "next_cursor": "MjAyNC0wMS0xNlQxNDo0NTowMC4wMDAwMDA=",
                        "has_more": False,
                    }
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin role required)"},
    },
)
async def list_invites(
    admin_user: AdminUser,
    invite_service: InviteServiceDep,
    cursor: Annotated[str | None, Query(description="Cursor for pagination")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Number of items per page")] = 50,
) -> PaginatedResponse[InviteRead]:
    """List pending invites for the tenant.

    Uses cursor-based pagination for efficient traversal of large result sets.
    Pass the `next_cursor` from a response to get the next page.
    """
    invites, next_cursor, has_more = await invite_service.list_pending_invites(cursor, limit)
    return PaginatedResponse(
        items=[InviteRead.model_validate(inv) for inv in invites],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get(
    "/{invite_id}",
    response_model=InviteRead,
    summary="Get invite by ID",
    description="Get details of a specific invite. Admin role required.",
    responses={
        200: {
            "description": "Invite details",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "newuser@example.com",
                        "role": "member",
                        "status": "pending",
                        "expires_at": "2024-01-22T10:30:00Z",
                        "created_at": "2024-01-15T10:30:00Z",
                    }
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin role required)"},
        404: {"description": "Invite not found"},
    },
)
async def get_invite(
    invite_id: UUID,
    admin_user: AdminUser,
    invite_service: InviteServiceDep,
) -> InviteRead:
    """Get invite by ID."""
    invite = await invite_service.get_invite_by_id(invite_id)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found",
        )
    return InviteRead.model_validate(invite)


@router.delete(
    "/{invite_id}",
    response_model=InviteCancelResponse,
    summary="Cancel invite",
    description="Cancel a pending invite. Admin role required.",
    responses={
        200: {
            "description": "Invite cancelled",
            "content": {
                "application/json": {"example": {"message": "Invite cancelled successfully"}}
            },
        },
        400: {"description": "Invite already accepted or cancelled"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin role required)"},
    },
)
async def cancel_invite(
    invite_id: UUID,
    admin_user: AdminUser,
    invite_service: InviteServiceDep,
) -> InviteCancelResponse:
    """Cancel a pending invite."""
    try:
        await invite_service.cancel_invite(invite_id)
        return InviteCancelResponse()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.put(
    "/{invite_id}",
    response_model=InviteCreateResponse,
    summary="Resend invite",
    description="Resend an invite (generates new token, invalidates old). Admin role required.",
    responses={
        200: {
            "description": "Invite resent with new token",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "email": "newuser@example.com",
                        "role": "member",
                        "expires_at": "2024-01-29T10:30:00Z",
                        "message": "Invite resent successfully",
                    }
                }
            },
        },
        400: {"description": "Invite already accepted or cancelled"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin role required)"},
    },
)
async def resend_invite(
    invite_id: UUID,
    admin_user: AdminUser,
    invite_service: InviteServiceDep,
) -> InviteCreateResponse:
    """Resend an invite with a new token."""
    try:
        invite, _ = await invite_service.resend_invite(
            invite_id=invite_id,
            resent_by_user_id=admin_user.id,
        )
        return InviteCreateResponse(
            id=invite.id,
            email=invite.email,
            role=invite.role,
            expires_at=invite.expires_at,
            message="Invite resent successfully",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# =============================================================================
# Public Endpoints (token-based, no tenant context required)
# =============================================================================


@router.get(
    "/t/{token}",
    response_model=InviteInfoResponse,
    summary="Get invite info by token",
    description="Get public information about an invite for display on accept page.",
    responses={
        200: {
            "description": "Invite information for accept page",
            "content": {
                "application/json": {
                    "example": {
                        "tenant_name": "Acme Corporation",
                        "email": "newuser@example.com",
                        "role": "member",
                        "expires_at": "2024-01-22T10:30:00Z",
                        "invited_by_name": "John Doe",
                    }
                }
            },
        },
        404: {"description": "Invalid or expired invite"},
    },
)
@limiter.limit("10/minute")
async def get_invite_info(
    request: Request,
    token: str,
    invite_service: InviteServicePublicDep,
) -> InviteInfoResponse:
    """Get invite info by token (for accept page UI)."""
    info = await invite_service.get_invite_info(token)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invite",
        )
    return InviteInfoResponse(**info)


@router.post(
    "/t/{token}/accept",
    response_model=AcceptInviteResponse,
    summary="Accept invite",
    description="Accept an invite and create a new account. Users can only belong to one tenant.",
    responses={
        200: {
            "description": "Invite accepted, account created",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Account created and joined tenant successfully",
                        "tenant_slug": "acme-corp",
                        "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request, email already registered, or invite already accepted"
        },
        404: {"description": "Invalid or expired invite"},
    },
)
@limiter.limit("5/hour")
async def accept_invite(
    request: Request,
    token: str,
    invite_service: InviteServicePublicDep,
    body: AcceptInviteRequest,
) -> AcceptInviteResponse:
    """Accept an invite and create a new account.

    Users can only belong to one tenant. If the email is already registered,
    the request will be rejected.
    """
    try:
        invite, user, tenant = await invite_service.accept_invite(
            token=token,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
        )
        return AcceptInviteResponse(
            message="Account created and joined tenant successfully",
            tenant_slug=tenant.slug,
            user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
