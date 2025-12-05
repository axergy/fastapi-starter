"""Authentication-related models - tokens and invites."""

from datetime import datetime
from uuid import UUID, uuid7

from sqlmodel import Field, SQLModel

from src.app.models.base import utc_now
from src.app.models.enums import InviteStatus, MembershipRole


class RefreshToken(SQLModel, table=True):
    """Refresh token storage - centralized in public schema."""

    __tablename__ = "refresh_tokens"
    __table_args__ = {"schema": "public"}

    id: UUID = Field(default_factory=uuid7, primary_key=True)
    user_id: UUID = Field(foreign_key="public.users.id", index=True)
    tenant_id: UUID = Field(foreign_key="public.tenants.id", index=True)
    token_hash: str = Field(max_length=255, unique=True, index=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=utc_now)
    revoked: bool = Field(default=False)


class EmailVerificationToken(SQLModel, table=True):
    """Email verification token storage."""

    __tablename__ = "email_verification_tokens"
    __table_args__ = {"schema": "public"}

    id: UUID = Field(default_factory=uuid7, primary_key=True)
    user_id: UUID = Field(foreign_key="public.users.id", index=True)
    token_hash: str = Field(max_length=255, unique=True, index=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=utc_now)
    used: bool = Field(default=False)
    used_at: datetime | None = Field(default=None)


class TenantInvite(SQLModel, table=True):
    """Tenant invite token storage."""

    __tablename__ = "tenant_invites"
    __table_args__ = {"schema": "public"}

    id: UUID = Field(default_factory=uuid7, primary_key=True)
    tenant_id: UUID = Field(foreign_key="public.tenants.id", index=True)
    email: str = Field(max_length=255, index=True)
    token_hash: str = Field(max_length=255, unique=True, index=True)
    role: str = Field(default=MembershipRole.MEMBER.value, max_length=50)
    invited_by_user_id: UUID = Field(foreign_key="public.users.id", index=True)
    status: str = Field(default=InviteStatus.PENDING.value, max_length=20)
    expires_at: datetime
    created_at: datetime = Field(default_factory=utc_now)
    accepted_at: datetime | None = Field(default=None)
    accepted_by_user_id: UUID | None = Field(foreign_key="public.users.id", default=None)
