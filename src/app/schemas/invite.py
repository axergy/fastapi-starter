"""Invite schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator
from zxcvbn import zxcvbn

from src.app.schemas.auth import MIN_PASSWORD_SCORE


class InviteCreateRequest(BaseModel):
    """Request to create an invite."""

    email: EmailStr
    role: Literal["admin", "member"] = "member"


class InviteCreateResponse(BaseModel):
    """Response after creating an invite."""

    id: UUID
    email: str
    role: str
    expires_at: datetime
    message: str = "Invite sent successfully"


class InviteRead(BaseModel):
    """Read model for invites (admin view)."""

    id: UUID
    email: str
    role: str
    status: str
    created_at: datetime
    expires_at: datetime
    invited_by_user_id: UUID

    model_config = {"from_attributes": True}


class InviteListResponse(BaseModel):
    """Response for listing invites."""

    invites: list[InviteRead]
    total: int


class InviteInfoResponse(BaseModel):
    """Public info about an invite (for accept page)."""

    email: str
    tenant_name: str
    tenant_slug: str | None
    role: str
    expires_at: datetime


class AcceptInviteRequest(BaseModel):
    """Accept invite and create new account."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    full_name: str = Field(min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength using zxcvbn."""
        result = zxcvbn(v)
        if result["score"] < MIN_PASSWORD_SCORE:
            feedback = result.get("feedback", {})
            warning = feedback.get("warning", "")
            suggestions = feedback.get("suggestions", [])
            if warning:
                raise ValueError(f"Weak password: {warning}")
            elif suggestions:
                raise ValueError(f"Weak password: {suggestions[0]}")
            else:
                raise ValueError("Password is too weak.")
        return v


class AcceptInviteResponse(BaseModel):
    """Response after accepting an invite."""

    message: str
    tenant_slug: str
    user_id: UUID


class InviteCancelResponse(BaseModel):
    """Response after cancelling an invite."""

    message: str = "Invite cancelled successfully"
