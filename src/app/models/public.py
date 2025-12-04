"""Public schema models - Lobby Pattern.

All user identity and authentication models live here.
Tenant-specific data models go in tenant.py.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from src.app.models.base import utc_now


class TenantStatus(str, Enum):
    """Tenant provisioning status."""

    PROVISIONING = "provisioning"
    READY = "ready"
    FAILED = "failed"


class MembershipRole(str, Enum):
    """User role within a tenant."""

    ADMIN = "admin"
    MEMBER = "member"


class Tenant(SQLModel, table=True):
    """Tenant registry in public schema."""

    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=100, index=True)
    slug: str = Field(max_length=50, unique=True, index=True)
    status: str = Field(default=TenantStatus.PROVISIONING.value)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def schema_name(self) -> str:
        return f"tenant_{self.slug}"

    @property
    def status_enum(self) -> TenantStatus:
        """Get status as TenantStatus enum."""
        return TenantStatus(self.status)


class User(SQLModel, table=True):
    """User model - centralized in public schema (Lobby Pattern)."""

    __tablename__ = "users"
    __table_args__ = {"schema": "public"}

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(max_length=255, unique=True, index=True)
    hashed_password: str = Field(max_length=255)
    full_name: str = Field(max_length=100)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
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


class RefreshToken(SQLModel, table=True):
    """Refresh token storage - centralized in public schema."""

    __tablename__ = "refresh_tokens"
    __table_args__ = {"schema": "public"}

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="public.users.id", index=True)
    tenant_id: UUID = Field(foreign_key="public.tenants.id", index=True)
    token_hash: str = Field(max_length=255, unique=True, index=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=utc_now)
    revoked: bool = Field(default=False)
