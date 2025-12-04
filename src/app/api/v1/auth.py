"""Authentication endpoints - Lobby Pattern."""

from fastapi import APIRouter, HTTPException, status
from starlette.requests import Request

from src.app.api.dependencies import AuthServiceDep, RegistrationServiceDep
from src.app.core.rate_limit import limiter
from src.app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
)
from src.app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        200: {
            "description": "Successful authentication",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer"
                    }
                }
            }
        },
        401: {"description": "Invalid credentials"},
        403: {"description": "User not member of tenant"}
    }
)
@limiter.limit("5/minute")
async def login(
    request: Request, login_data: LoginRequest, service: AuthServiceDep
) -> LoginResponse:
    """Authenticate user and return tokens.

    Requires X-Tenant-ID header. User must have membership in the tenant.
    """
    result = await service.authenticate(login_data.email, login_data.password)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or no access to tenant",
        )

    return result


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    responses={
        200: {
            "description": "Token refreshed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                    }
                }
            }
        },
        401: {"description": "Invalid or expired refresh token"}
    }
)
async def refresh(request: RefreshRequest, service: AuthServiceDep) -> RefreshResponse:
    """Refresh access token using refresh token."""
    access_token = await service.refresh_access_token(request.refresh_token)

    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return RefreshResponse(access_token=access_token)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {
            "description": "Registration initiated",
            "content": {
                "application/json": {
                    "example": {
                        "user": {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "email": "user@example.com",
                            "full_name": "John Doe",
                            "is_active": True,
                            "is_superuser": False
                        },
                        "workflow_id": "tenant-provisioning-acme-corp",
                        "tenant_slug": "acme-corp"
                    }
                }
            }
        },
        409: {"description": "Validation error or tenant slug already exists"}
    }
)
@limiter.limit("3/hour")
async def register(
    request: Request,
    register_data: RegisterRequest,
    service: RegistrationServiceDep,
) -> RegisterResponse:
    """Register new user AND create a new tenant.

    Does NOT require X-Tenant-ID header.
    Returns user info and workflow_id to poll for tenant status.
    """
    try:
        user, workflow_id = await service.register(
            email=register_data.email,
            password=register_data.password,
            full_name=register_data.full_name,
            tenant_name=register_data.tenant_name,
            tenant_slug=register_data.tenant_slug,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    return RegisterResponse(
        user=UserRead.model_validate(user),
        workflow_id=workflow_id,
        tenant_slug=register_data.tenant_slug,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: RefreshRequest, service: AuthServiceDep) -> None:
    """Revoke refresh token (logout)."""
    await service.revoke_refresh_token(request.refresh_token)
