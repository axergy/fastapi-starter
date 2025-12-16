import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=56)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", v):
            raise ValueError(
                "Slug must start with a letter and contain only lowercase "
                "letters, numbers, and single underscores as separators"
            )
        return v


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
