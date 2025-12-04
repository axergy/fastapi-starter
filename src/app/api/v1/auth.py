from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.app.api.dependencies import DBSession, get_tenant_id_from_header
from src.app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
)
from src.app.schemas.user import UserRead
from src.app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    session: DBSession,
    tenant_id: Annotated[str, Depends(get_tenant_id_from_header)],
) -> LoginResponse:
    """Authenticate user and return tokens."""
    service = AuthService(session, tenant_id)
    result = await service.authenticate(request.email, request.password)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return result


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    request: RefreshRequest,
    session: DBSession,
    tenant_id: Annotated[str, Depends(get_tenant_id_from_header)],
) -> RefreshResponse:
    """Refresh access token using refresh token."""
    service = AuthService(session, tenant_id)
    access_token = await service.refresh_access_token(request.refresh_token)

    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return RefreshResponse(access_token=access_token)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    session: DBSession,
    tenant_id: Annotated[str, Depends(get_tenant_id_from_header)],
) -> UserRead:
    """Register new user."""
    service = AuthService(session, tenant_id)
    user = await service.register_user(
        email=request.email,
        password=request.password,
        full_name=request.full_name,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    return UserRead.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: RefreshRequest,
    session: DBSession,
    tenant_id: Annotated[str, Depends(get_tenant_id_from_header)],
) -> None:
    """Revoke refresh token (logout)."""
    service = AuthService(session, tenant_id)
    await service.revoke_refresh_token(request.refresh_token)
