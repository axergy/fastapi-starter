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


async def get_db_session(
    tenant_schema: Annotated[str, Depends(get_tenant_schema)],
) -> AsyncGenerator[AsyncSession, None]:
    """Get database session scoped to tenant."""
    async with get_tenant_session(tenant_schema) as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db_session)]


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

    if payload.get("type") != "access":
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
