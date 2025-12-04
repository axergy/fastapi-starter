"""FastAPI dependency injection definitions."""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.app.core.db import get_public_session, get_tenant_session
from src.app.core.security import decode_token
from src.app.models.public import Tenant
from src.app.models.tenant import User
from src.app.repositories.tenant_repository import TenantRepository
from src.app.repositories.token_repository import RefreshTokenRepository
from src.app.repositories.user_repository import UserRepository
from src.app.services.auth_service import AuthService, TokenType
from src.app.services.tenant_service import TenantService
from src.app.services.user_service import UserService

# =============================================================================
# Tenant Header Dependencies
# =============================================================================


async def get_tenant_id_from_header(
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> str:
    """Extract tenant ID from header."""
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header is required",
        )
    return x_tenant_id


async def get_validated_tenant(
    tenant_id: Annotated[str, Depends(get_tenant_id_from_header)],
) -> Tenant:
    """Validate tenant exists and is active."""
    async with get_public_session() as session:
        result = await session.execute(select(Tenant).where(Tenant.slug == tenant_id))
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

        return tenant


async def get_tenant_schema(
    tenant: Annotated[Tenant, Depends(get_validated_tenant)],
) -> str:
    """Get the schema name for the validated tenant."""
    return tenant.schema_name


# =============================================================================
# Database Session Dependencies
# =============================================================================


async def get_db_session(
    tenant_schema: Annotated[str, Depends(get_tenant_schema)],
) -> AsyncGenerator[AsyncSession, None]:
    """Get database session scoped to tenant."""
    async with get_tenant_session(tenant_schema) as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_public_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for public schema."""
    async with get_public_session() as session:
        yield session


PublicDBSession = Annotated[AsyncSession, Depends(get_public_db_session)]


# =============================================================================
# Repository Dependencies
# =============================================================================


def get_user_repository(session: DBSession) -> UserRepository:
    """Get user repository with tenant-scoped session."""
    return UserRepository(session)


def get_token_repository(session: DBSession) -> RefreshTokenRepository:
    """Get refresh token repository with tenant-scoped session."""
    return RefreshTokenRepository(session)


def get_tenant_repository(session: PublicDBSession) -> TenantRepository:
    """Get tenant repository with public schema session."""
    return TenantRepository(session)


UserRepo = Annotated[UserRepository, Depends(get_user_repository)]
TokenRepo = Annotated[RefreshTokenRepository, Depends(get_token_repository)]
TenantRepo = Annotated[TenantRepository, Depends(get_tenant_repository)]


# =============================================================================
# Service Dependencies
# =============================================================================


def get_user_service(user_repo: UserRepo) -> UserService:
    """Get user service."""
    return UserService(user_repo)


def get_auth_service(
    user_repo: UserRepo,
    token_repo: TokenRepo,
    tenant_id: Annotated[str, Depends(get_tenant_id_from_header)],
) -> AuthService:
    """Get auth service with repositories and tenant context."""
    return AuthService(user_repo, token_repo, tenant_id)


def get_tenant_service(tenant_repo: TenantRepo) -> TenantService:
    """Get tenant service."""
    return TenantService(tenant_repo)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]


# =============================================================================
# Authentication Dependencies
# =============================================================================


async def get_current_user(
    session: DBSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Validate access token and return current user."""
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

    result = await session.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
