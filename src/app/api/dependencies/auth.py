"""Authentication and authorization dependencies."""

import contextlib
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import select

from src.app.api.context import (
    AssumedIdentityContext,
    get_assumed_identity_context,
)
from src.app.api.dependencies.db import DBSession
from src.app.api.dependencies.tenant import ValidatedTenant
from src.app.core.logging import bind_user_context
from src.app.core.security import decode_token
from src.app.models import MembershipRole, User, UserTenantMembership
from src.app.services.auth_service import TokenType
from src.app.services.user_service import UserService


async def _validate_access_token(
    authorization: str | None,
    user_service: UserService,
) -> tuple[dict[str, Any], User, AssumedIdentityContext | None]:
    """Validate access token and return (payload, user, assumed_identity_context).

    Common validation logic shared by get_current_user and get_authenticated_user.
    Validates: header format, token decode, token type, user_id, user exists + active.

    If the token contains assumed_identity claims, validates that the operator
    is still an active superuser and returns the assumed identity context.
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

    # Accept both regular access tokens and assumed identity tokens
    token_type = payload.get("type")
    if token_type not in (TokenType.ACCESS, TokenType.ASSUMED_ACCESS):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # If it's an assumed_access token, it MUST have assumed_identity claims
    if token_type == TokenType.ASSUMED_ACCESS and not payload.get("assumed_identity"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid assumed identity token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_uuid = UUID(user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user_id in token",
        ) from e

    # Use UserService instead of direct DB query
    user = await user_service.get_by_id(user_uuid)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Check for assumed identity claims
    assumed_identity_ctx = None
    assumed_identity_data = payload.get("assumed_identity")

    if assumed_identity_data:
        # Validate operator_user_id is present
        operator_user_id = assumed_identity_data.get("operator_user_id")
        if not operator_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid assumed identity token",
            )

        try:
            operator_user_uuid = UUID(operator_user_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid operator_user_id in token",
            ) from e

        # Verify operator is still an active superuser
        operator_user = await user_service.get_by_id(operator_user_uuid)
        if operator_user is None or not operator_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Operator user not found or inactive",
            )

        if not operator_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Assumed identity not authorized - operator is not a superuser",
            )

        # Parse started_at if present
        started_at = None
        if assumed_identity_data.get("started_at"):
            with contextlib.suppress(ValueError):
                started_at = datetime.fromisoformat(assumed_identity_data["started_at"])

        # Validate tenant_id
        try:
            token_tenant_id = UUID(str(payload.get("tenant_id", "")))
        except (ValueError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid tenant_id in token",
            ) from e

        # Build assumed identity context
        assumed_identity_ctx = AssumedIdentityContext(
            operator_user_id=operator_user_uuid,
            assumed_user_id=user_uuid,
            tenant_id=token_tenant_id,
            reason=assumed_identity_data.get("reason"),
            started_at=started_at,
        )

    return payload, user, assumed_identity_ctx


def _get_user_service(user_repo: "UserRepo", session: DBSession) -> UserService:
    """Create UserService for auth dependencies (avoids circular import)."""
    return UserService(user_repo, session)


# Import here to avoid circular dependency
from src.app.api.dependencies.repositories import UserRepo  # noqa: E402


async def get_current_user(
    session: DBSession,
    tenant: ValidatedTenant,
    user_repo: UserRepo,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Validate access token and return current user.

    IMPORTANT: Validates that JWT tenant_id matches the X-Tenant-ID header's tenant.

    For assumed identity tokens: returns the assumed user and sets the
    assumed identity context for audit logging.
    """
    user_service = _get_user_service(user_repo, session)
    payload, user, assumed_identity_ctx = await _validate_access_token(authorization, user_service)

    # CRITICAL: Validate JWT tenant_id matches X-Tenant-ID header's tenant
    token_tenant_id = payload.get("tenant_id")
    if not token_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

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

    # Note: Assumed identity context is set by RequestContextMiddleware
    # The operator superuser validation happens in _validate_access_token above

    # Bind user and tenant context to logs
    bind_user_context(user.id, tenant.id, user.email)

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_authenticated_user(
    session: DBSession,
    user_repo: UserRepo,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Validate access token and return user (no tenant context required).

    Used for tenant-agnostic endpoints like listing user's tenants.
    Does NOT validate tenant membership - just validates the token and user exists.
    """
    user_service = _get_user_service(user_repo, session)
    _, user, _ = await _validate_access_token(authorization, user_service)
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


def get_optional_assumed_identity_context() -> AssumedIdentityContext | None:
    """Get the assumed identity context if present.

    Use this dependency in routes that need to know if the current request
    is from an assumed identity session, for example to display a warning
    or to include additional context in responses.

    Returns:
        The AssumedIdentityContext if an identity assumption is active, None otherwise.
    """
    return get_assumed_identity_context()


OptionalAssumedIdentityContext = Annotated[
    AssumedIdentityContext | None, Depends(get_optional_assumed_identity_context)
]
