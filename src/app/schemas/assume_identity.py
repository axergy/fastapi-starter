"""Schemas for assumed identity (admin impersonation) feature."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AssumeIdentityRequest(BaseModel):
    """Request to assume a user's identity."""

    target_user_id: UUID = Field(description="ID of the user whose identity to assume")
    tenant_id: UUID = Field(description="ID of the tenant context for the assumed session")
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional reason for assuming the identity (for audit purposes)",
    )


class AssumeIdentityResponse(BaseModel):
    """Response containing the assumed identity session token."""

    access_token: str = Field(description="JWT token for the assumed identity session")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(
        description="Token expiry in seconds (default 15 minutes = 900 seconds)"
    )
    assumed_user_id: UUID = Field(description="ID of the user being assumed")
    assumed_user_email: str = Field(description="Email of the user being assumed")
    tenant_id: UUID = Field(description="ID of the tenant context")
    tenant_slug: str = Field(description="Slug of the tenant context")


class AssumedIdentityInfo(BaseModel):
    """Information about the current assumed identity session.

    Used for debugging and to display warnings in the UI when an admin
    is operating as another user.
    """

    is_assuming: bool = Field(
        description="Whether the current request is from an assumed identity session"
    )
    operator_user_id: UUID | None = Field(
        default=None, description="ID of the superuser performing the assumption"
    )
    operator_user_email: str | None = Field(
        default=None, description="Email of the superuser performing the assumption"
    )
    assumed_user_id: UUID | None = Field(
        default=None, description="ID of the user whose identity is assumed"
    )
    assumed_user_email: str | None = Field(
        default=None, description="Email of the user whose identity is assumed"
    )
    tenant_id: UUID | None = Field(default=None, description="ID of the tenant context")
    reason: str | None = Field(default=None, description="Reason provided for the assumption")
    started_at: datetime | None = Field(
        default=None, description="When the assumption session started"
    )
