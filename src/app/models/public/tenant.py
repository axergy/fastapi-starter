"""Tenant model - registry in public schema."""

from datetime import datetime
from uuid import UUID, uuid7

from sqlmodel import Field, SQLModel

from src.app.models.base import utc_now
from src.app.models.enums import TenantStatus


class Tenant(SQLModel, table=True):
    """Tenant registry in public schema."""

    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}

    id: UUID = Field(default_factory=uuid7, primary_key=True)
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
