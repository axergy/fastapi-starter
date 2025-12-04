"""Authentication endpoints - Lobby Pattern."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.app.api.dependencies import AuthServiceDep, DBSession, UserRepo
from src.app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
)
from src.app.schemas.user import UserRead
from src.app.services.registration_service import RegistrationService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_registration_service(user_repo: UserRepo, session: DBSession) -> RegistrationService:
    """Create registration service (no tenant context required)."""
    return RegistrationService(user_repo, session)


RegistrationServiceDep = Annotated[RegistrationService, Depends(get_registration_service)]


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, service: AuthServiceDep) -> LoginResponse:
    """Authenticate user and return tokens.

    Requires X-Tenant-ID header. User must have membership in the tenant.
    """
    result = await service.authenticate(request.email, request.password)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or no access to tenant",
        )

    return result


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(request: RefreshRequest, service: AuthServiceDep) -> RefreshResponse:
    """Refresh access token using refresh token."""
    access_token = await service.refresh_access_token(request.refresh_token)

    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return RefreshResponse(access_token=access_token)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_202_ACCEPTED)
async def register(
    request: RegisterRequest,
    service: RegistrationServiceDep,
) -> RegisterResponse:
    """Register new user AND create a new tenant.

    Does NOT require X-Tenant-ID header.
    Returns user info and workflow_id to poll for tenant status.
    """
    try:
        user, workflow_id = await service.register(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            tenant_name=request.tenant_name,
            tenant_slug=request.tenant_slug,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    return RegisterResponse(
        user=UserRead.model_validate(user),
        workflow_id=workflow_id,
        tenant_slug=request.tenant_slug,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: RefreshRequest, service: AuthServiceDep) -> None:
    """Revoke refresh token (logout)."""
    await service.revoke_refresh_token(request.refresh_token)
