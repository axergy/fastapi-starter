"""FastAPI dependency injection definitions - Lobby Pattern."""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.app.core.db import get_public_session
from src.app.core.security import decode_token
from src.app.models.public import Tenant, TenantStatus, User, UserTenantMembership
from src.app.repositories.membership_repository import MembershipRepository
from src.app.repositories.tenant_repository import TenantRepository
from src.app.repositories.token_repository import RefreshTokenRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.auth_service import AuthService, TokenType
from src.app.services.registration_service import RegistrationService
from src.app.services.tenant_service import TenantService
from src.app.services.user_service import UserService

# =============================================================================
# Tenant Header Dependencies
# =============================================================================


async def get_tenant_id_from_header(
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> str:
    """Extract tenant ID (slug) from header."""
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header is required",
        )
    return x_tenant_id


async def get_validated_tenant(
    tenant_slug: Annotated[str, Depends(get_tenant_id_from_header)],
) -> Tenant:
    """Validate tenant exists, is active, and is ready."""
    async with get_public_session() as session:
        result = await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        tenant = result.scalar_one_or_none()

        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )

        if not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant is inactive",
            )

        if tenant.status != TenantStatus.READY.value:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Tenant is {tenant.status}",
            )

        return tenant


ValidatedTenant = Annotated[Tenant, Depends(get_validated_tenant)]


# =============================================================================
# Database Session Dependencies (ALL USE PUBLIC SCHEMA - Lobby Pattern)
# =============================================================================


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for public schema (Lobby Pattern)."""
    async with get_public_session() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db_session)]

# Alias for clarity
PublicDBSession = DBSession


# =============================================================================
# Repository Dependencies
# =============================================================================


def get_user_repository(session: DBSession) -> UserRepository:
    """Get user repository with public schema session."""
    return UserRepository(session)


def get_token_repository(session: DBSession) -> RefreshTokenRepository:
    """Get refresh token repository with public schema session."""
    return RefreshTokenRepository(session)


def get_membership_repository(session: DBSession) -> MembershipRepository:
    """Get membership repository with public schema session."""
    return MembershipRepository(session)


def get_tenant_repository(session: DBSession) -> TenantRepository:
    """Get tenant repository with public schema session."""
    return TenantRepository(session)


UserRepo = Annotated[UserRepository, Depends(get_user_repository)]
TokenRepo = Annotated[RefreshTokenRepository, Depends(get_token_repository)]
MembershipRepo = Annotated[MembershipRepository, Depends(get_membership_repository)]
TenantRepo = Annotated[TenantRepository, Depends(get_tenant_repository)]


# =============================================================================
# Service Dependencies
# =============================================================================


def get_user_service(user_repo: UserRepo, session: DBSession) -> UserService:
    """Get user service."""
    return UserService(user_repo, session)


def get_auth_service(
    user_repo: UserRepo,
    token_repo: TokenRepo,
    membership_repo: MembershipRepo,
    session: DBSession,
    tenant: ValidatedTenant,
) -> AuthService:
    """Get auth service with repositories and tenant context."""
    return AuthService(
        user_repo,
        token_repo,
        membership_repo,
        session,
        tenant.id,  # Pass UUID, not slug
    )


def get_tenant_service(tenant_repo: TenantRepo, session: DBSession) -> TenantService:
    """Get tenant service."""
    return TenantService(tenant_repo, session)


def get_registration_service(user_repo: UserRepo, session: DBSession) -> RegistrationService:
    """Get registration service (no tenant context required)."""
    return RegistrationService(user_repo, session)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]
RegistrationServiceDep = Annotated[RegistrationService, Depends(get_registration_service)]


# =============================================================================
# Authentication Dependencies
# =============================================================================


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
