"""Audit log schemas for API responses."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditLogRead(BaseModel):
    """Audit log entry for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    changes: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    status: str
    error_message: str | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated audit log response."""

    items: list[AuditLogRead]
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for fetching the next page. None if no more pages.",
    )
    has_more: bool = Field(
        default=False,
        description="Whether there are more items after this page.",
    )
