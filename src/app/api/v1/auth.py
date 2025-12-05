"""Authentication endpoints - Lobby Pattern."""

from fastapi import APIRouter, HTTPException, status
from starlette.requests import Request

from src.app.api.dependencies import (
    AuthServiceDep,
    EmailVerificationServiceDep,
    RegistrationServiceDep,
)
from src.app.core.rate_limit import limiter
from src.app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
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
                        "token_type": "bearer",
                    }
                }
            },
        },
        401: {"description": "Invalid credentials"},
        403: {"description": "Email not verified or user not member of tenant"},
    },
)
@limiter.limit("5/minute")
async def login(
    request: Request, login_data: LoginRequest, service: AuthServiceDep
) -> LoginResponse:
    """Authenticate user and return tokens.

    Requires X-Tenant-ID header. User must have membership in the tenant.
    User must have verified their email address.
    """
    try:
        result = await service.authenticate(login_data.email, login_data.password)
    except ValueError as e:
        if str(e) == "Email not verified":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email not verified. Please check your email for verification link.",
            ) from e
        raise

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
            "description": "Token refreshed successfully with token rotation",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    }
                }
            },
        },
        401: {"description": "Invalid or expired refresh token"},
    },
)
@limiter.limit("10/minute")
async def refresh(
    request: Request, refresh_data: RefreshRequest, service: AuthServiceDep
) -> RefreshResponse:
    """Refresh access token using refresh token.

    Implements token rotation: returns both a new access token AND a new refresh token.
    The old refresh token is atomically revoked to prevent replay attacks.
    """
    result = await service.refresh_access_token(refresh_data.refresh_token)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    access_token, refresh_token = result
    return RefreshResponse(access_token=access_token, refresh_token=refresh_token)


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
                            "is_superuser": False,
                        },
                        "workflow_id": "tenant-provisioning-acme-corp",
                        "tenant_slug": "acme-corp",
                    }
                }
            },
        },
        409: {"description": "Validation error or tenant slug already exists"},
    },
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
@limiter.limit("5/minute")
async def logout(request: Request, logout_data: RefreshRequest, service: AuthServiceDep) -> None:
    """Revoke refresh token (logout)."""
    await service.revoke_refresh_token(logout_data.refresh_token)


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    responses={
        200: {
            "description": "Email verified successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Email verified successfully",
                        "verified": True,
                        "user": {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "email": "user@example.com",
                            "full_name": "John Doe",
                        },
                    }
                }
            },
        },
        400: {"description": "Invalid or expired token"},
    },
)
async def verify_email(
    request: Request,
    verify_data: VerifyEmailRequest,
    service: EmailVerificationServiceDep,
) -> VerifyEmailResponse:
    """Verify email address using token from verification email.

    Does NOT require X-Tenant-ID header or authentication.
    """
    user = await service.verify_token(verify_data.token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    return VerifyEmailResponse(
        message="Email verified successfully",
        verified=True,
        user=UserRead.model_validate(user),
    )


@router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
    responses={
        200: {
            "description": "Verification email sent (same response if user not found)",
            "content": {
                "application/json": {
                    "example": {
                        "message": "If an account exists, a verification link has been sent"
                    }
                }
            },
        },
    },
)
@limiter.limit("3/hour")
async def resend_verification(
    request: Request,
    resend_data: ResendVerificationRequest,
    service: EmailVerificationServiceDep,
) -> ResendVerificationResponse:
    """Resend verification email.

    Does NOT require X-Tenant-ID header or authentication.
    Rate limited to 3 per hour to prevent abuse.
    Always returns success to prevent email enumeration.
    """
    await service.resend_verification(resend_data.email)

    return ResendVerificationResponse(
        message="If an account exists with this email, a verification link has been sent"
    )
