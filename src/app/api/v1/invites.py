"""Tenant invite API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from src.app.api.dependencies import (
    AdminUser,
    DBSession,
    InviteServiceDep,
    InviteServicePublicDep,
)
from src.app.schemas.invite import (
    AcceptInviteExistingUser,
    AcceptInviteNewUser,
    AcceptInviteResponse,
    InviteCancelResponse,
    InviteCreateRequest,
    InviteCreateResponse,
    InviteInfoResponse,
    InviteListResponse,
    InviteRead,
)

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
    response_model=InviteListResponse,
    summary="List pending invites",
    description="List all pending invites for the tenant. Admin role required.",
)
async def list_invites(
    admin_user: AdminUser,
    invite_service: InviteServiceDep,
    limit: int = 100,
    offset: int = 0,
) -> InviteListResponse:
    """List pending invites for the tenant."""
    invites = await invite_service.list_pending_invites(limit=limit, offset=offset)
    return InviteListResponse(
        invites=[InviteRead.model_validate(inv) for inv in invites],
        total=len(invites),
    )


@router.get(
    "/{invite_id}",
    response_model=InviteRead,
    summary="Get invite by ID",
    description="Get details of a specific invite. Admin role required.",
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
)
async def get_invite_info(
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


class AcceptInviteRequestBody(BaseModel):
    """Accept invite request with discriminated union."""

    data: AcceptInviteExistingUser | AcceptInviteNewUser


@router.post(
    "/t/{token}/accept",
    response_model=AcceptInviteResponse,
    summary="Accept invite",
    description=(
        "Accept an invite. For existing users, include Authorization header. "
        "For new users, include email, password, and full_name in body."
    ),
)
async def accept_invite(
    token: str,
    invite_service: InviteServicePublicDep,
    session: DBSession,
    body: AcceptInviteExistingUser | AcceptInviteNewUser | None = None,
    authorization: Annotated[str | None, Header()] = None,
) -> AcceptInviteResponse:
    """Accept an invite.

    Two modes:
    1. Existing user: Include Authorization header, body can be empty or {"type": "existing"}
    2. New user: Include {"type": "new", "email": "...", "password": "...", "full_name": "..."}
    """
    # Import here to avoid circular dependency
    from sqlmodel import select

    from src.app.core.security import decode_token
    from src.app.models.public import User
    from src.app.repositories import TenantRepository
    from src.app.services.auth_service import TokenType

    # Determine if this is an existing user (has valid auth) or new user
    if authorization and authorization.startswith("Bearer "):
        # Existing user flow
        auth_token = authorization[7:]
        payload = decode_token(auth_token)

        if payload is None or payload.get("type") != TokenType.ACCESS:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        # Get user
        from uuid import UUID as UUIDType

        try:
            user_uuid = UUIDType(user_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user_id in token",
            ) from e

        result = await session.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        try:
            invite, accepted_user = await invite_service.accept_invite_existing_user(
                token=token,
                user=user,
            )
            # Get tenant slug
            tenant_repo = TenantRepository(session)
            tenant = await tenant_repo.get_by_id(invite.tenant_id)
            return AcceptInviteResponse(
                message="Successfully joined tenant",
                tenant_slug=tenant.slug if tenant else "",
                user_id=accepted_user.id,
                is_new_user=False,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

    # New user flow - body must contain registration data
    if body is None or isinstance(body, AcceptInviteExistingUser):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auth header required for existing users, or provide registration data",
        )

    if not isinstance(body, AcceptInviteNewUser):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request body",
        )

    try:
        invite, new_user = await invite_service.accept_invite_new_user(
            token=token,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
        )
        # Get tenant slug
        tenant_repo = TenantRepository(session)
        tenant = await tenant_repo.get_by_id(invite.tenant_id)
        return AcceptInviteResponse(
            message="Account created and joined tenant successfully",
            tenant_slug=tenant.slug if tenant else "",
            user_id=new_user.id,
            is_new_user=True,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
