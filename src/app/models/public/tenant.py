"""Tenant model - registry in public schema."""

from datetime import datetime
from uuid import UUID, uuid7

from sqlmodel import Field, SQLModel

from src.app.core.security.validators import (
    MAX_TENANT_SLUG_LENGTH,
    TENANT_SCHEMA_PREFIX,
    validate_schema_name,
)
from src.app.models.base import utc_now
from src.app.models.enums import TenantStatus


class Tenant(SQLModel, table=True):
    """Tenant registry in public schema."""

    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}

    id: UUID = Field(default_factory=uuid7, primary_key=True)
    name: str = Field(max_length=100, index=True)
    slug: str = Field(max_length=MAX_TENANT_SLUG_LENGTH, unique=True, index=True)
    status: str = Field(default=TenantStatus.PROVISIONING.value)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)
    deleted_at: datetime | None = Field(default=None)

    @property
    def schema_name(self) -> str:
        """Get the schema name for this tenant.

        Returns:
            Schema name in format 'tenant_{slug}'

        Raises:
            ValueError: If the resulting schema name exceeds PostgreSQL's 63-char limit
                or contains invalid characters
        """
        name = f"{TENANT_SCHEMA_PREFIX}{self.slug}"
        validate_schema_name(name)
        return name

    @property
    def status_enum(self) -> TenantStatus:
        """Get status as TenantStatus enum."""
        return TenantStatus(self.status)

    @property
    def is_deleted(self) -> bool:
        """Check if tenant is soft-deleted."""
        return self.deleted_at is not None
