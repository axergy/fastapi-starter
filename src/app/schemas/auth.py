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
