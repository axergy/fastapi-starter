import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from src.app.schemas.user import UserRead


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
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    """Registration creates user + new tenant (Lobby Pattern)."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    full_name: str = Field(min_length=1, max_length=100)
    tenant_name: str = Field(min_length=1, max_length=100)
    tenant_slug: str = Field(min_length=1, max_length=50)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Ensure password has minimum complexity."""
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")

        # Check against common passwords
        common_passwords = ["password", "12345678", "qwerty123", "Password1"]
        if v.lower() in [p.lower() for p in common_passwords]:
            raise ValueError("Password is too common")

        return v

    @field_validator("tenant_slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9_]+$", v):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and underscores"
            )
        return v


class RegisterResponse(BaseModel):
    """Registration response - includes workflow_id to poll for tenant status."""

    user: UserRead
    workflow_id: str
    tenant_slug: str
