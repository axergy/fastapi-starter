import re

from pydantic import BaseModel, EmailStr, Field, field_validator
from zxcvbn import zxcvbn

from src.app.schemas.user import UserRead

# Minimum zxcvbn score (0-4 scale): 3 = "safely unguessable"
MIN_PASSWORD_SCORE = 3


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    """Registration creates user + new tenant (Lobby Pattern)."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    full_name: str = Field(min_length=1, max_length=100)
    tenant_name: str = Field(min_length=1, max_length=100)
    # Max 56 chars: 63 (PostgreSQL limit) - 7 (len("tenant_"))
    tenant_slug: str = Field(
        min_length=1,
        max_length=56,
        json_schema_extra={
            "examples": ["acme_corp", "my_company"],
            "description": "Tenant identifier. Lowercase alphanumeric with underscores.",
        },
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength using zxcvbn entropy estimation."""
        result = zxcvbn(v)
        score = result["score"]  # 0-4 scale

        if score < MIN_PASSWORD_SCORE:
            # Get helpful feedback from zxcvbn
            feedback = result.get("feedback", {})
            warning = feedback.get("warning", "")
            suggestions = feedback.get("suggestions", [])

            if warning:
                raise ValueError(f"Weak password: {warning}")
            elif suggestions:
                raise ValueError(f"Weak password: {suggestions[0]}")
            else:
                raise ValueError(
                    "Password is too weak. Use a longer password with a mix of characters."
                )

        return v

    @field_validator("tenant_slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", v):
            raise ValueError(
                "Slug must start with a letter and contain only lowercase "
                "letters, numbers, and single underscores as separators"
            )
        return v


class RegisterResponse(BaseModel):
    """Registration response - includes workflow_id to poll for tenant status."""

    user: UserRead
    workflow_id: str
    tenant_slug: str
    message: str = "Please check your email to verify your account"


class VerifyEmailRequest(BaseModel):
    """Request to verify email with token."""

    token: str = Field(min_length=32, max_length=128)


class VerifyEmailResponse(BaseModel):
    """Response after email verification."""

    message: str
    verified: bool
    user: UserRead | None = None


class ResendVerificationRequest(BaseModel):
    """Request to resend verification email."""

    email: EmailStr


class ResendVerificationResponse(BaseModel):
    """Response after resending verification email."""

    message: str
