"""Authentication and authorization dependencies."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import select

from src.app.api.dependencies.db import DBSession
from src.app.api.dependencies.tenant import ValidatedTenant
from src.app.core.security import decode_token
from src.app.models import MembershipRole, User, UserTenantMembership
from src.app.services.auth_service import TokenType


async def get_current_user(
    session: DBSession,
    tenant: ValidatedTenant,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Validate access token and return current user.

    IMPORTANT: Validates that JWT tenant_id matches the X-Tenant-ID header's tenant.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    token = authorization[7:]
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("type") != TokenType.ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    token_tenant_id = payload.get("tenant_id")

    if not user_id or not token_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # CRITICAL: Validate JWT tenant_id matches X-Tenant-ID header's tenant
    try:
        token_tenant_uuid = UUID(token_tenant_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant_id in token",
        ) from e

    if token_tenant_uuid != tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token tenant does not match request tenant",
        )

    # Validate user_id format
    try:
        user_uuid = UUID(user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user_id in token",
        ) from e

    # Get user from public schema
    result = await session.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Verify user has active membership in this tenant
    membership_result = await session.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == user.id,
            UserTenantMembership.tenant_id == tenant.id,
            UserTenantMembership.is_active == True,  # noqa: E712
        )
    )
    membership = membership_result.scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to this tenant",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_authenticated_user(
    session: DBSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Validate access token and return user (no tenant context required).

    Used for tenant-agnostic endpoints like listing user's tenants.
    Does NOT validate tenant membership - just validates the token and user exists.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    token = authorization[7:]
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("type") != TokenType.ACCESS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Validate user_id format
    try:
        user_uuid = UUID(user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user_id in token",
        ) from e

    # Get user from public schema
    result = await session.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


AuthenticatedUser = Annotated[User, Depends(get_authenticated_user)]


async def require_admin_role(
    current_user: CurrentUser,
    tenant: ValidatedTenant,
    session: DBSession,
) -> User:
    """Require the current user to have admin role in the tenant.

    This dependency should be used for admin-only endpoints.
    """
    # Get user's membership in this tenant
    result = await session.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == current_user.id,
            UserTenantMembership.tenant_id == tenant.id,
            UserTenantMembership.is_active == True,  # noqa: E712
        )
    )
    membership = result.scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to this tenant",
        )

    if membership.role != MembershipRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for this operation",
        )

    return current_user


AdminUser = Annotated[User, Depends(require_admin_role)]


async def require_superuser(
    user: AuthenticatedUser,
) -> User:
    """Require the current user to be a superuser.

    This dependency should be used for platform-wide admin endpoints.
    Does not require tenant context - superusers operate across all tenants.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return user


SuperUser = Annotated[User, Depends(require_superuser)]
