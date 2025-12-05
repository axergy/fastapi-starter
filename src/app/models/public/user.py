"""User models - centralized in public schema (Lobby Pattern)."""

from datetime import datetime
from uuid import UUID, uuid7

from sqlmodel import Field, SQLModel

from src.app.models.base import utc_now
from src.app.models.enums import MembershipRole


class User(SQLModel, table=True):
    """User model - centralized in public schema (Lobby Pattern)."""

    __tablename__ = "users"
    __table_args__ = {"schema": "public"}

    id: UUID = Field(default_factory=uuid7, primary_key=True)
    email: str = Field(max_length=255, unique=True, index=True)
    hashed_password: str = Field(max_length=255)
    full_name: str = Field(max_length=100)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    email_verified: bool = Field(default=False)
    email_verified_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class UserTenantMembership(SQLModel, table=True):
    """Junction table for user-tenant membership."""

    __tablename__ = "user_tenant_membership"
    __table_args__ = {"schema": "public"}

    user_id: UUID = Field(foreign_key="public.users.id", primary_key=True)
    tenant_id: UUID = Field(foreign_key="public.tenants.id", primary_key=True)
    role: str = Field(default=MembershipRole.MEMBER.value, max_length=50)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)
