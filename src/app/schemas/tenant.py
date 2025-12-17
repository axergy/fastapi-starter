from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.app.core.security.validators import (
    MAX_TENANT_SLUG_LENGTH,
    validate_tenant_slug_format,
)


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(
        min_length=1,
        max_length=MAX_TENANT_SLUG_LENGTH,
        json_schema_extra={
            "examples": ["acme_corp", "my_company", "tenant_123"],
            "description": "Lowercase alphanumeric with underscores only. No hyphens.",
        },
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        return validate_tenant_slug_format(v)


class TenantRead(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    is_active: bool
    created_at: datetime
    deleted_at: datetime | None = None

    model_config = {"from_attributes": True}


class TenantProvisioningResponse(BaseModel):
    """Response when tenant provisioning workflow is started."""

    workflow_id: str
    slug: str
    status: str = "provisioning"


class TenantStatusResponse(BaseModel):
    """Response for tenant provisioning status check."""

    status: str  # "provisioning", "ready", "failed"
    tenant: TenantRead | None = None
    error: str | None = None
