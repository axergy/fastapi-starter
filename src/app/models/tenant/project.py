"""Project model - tenant-scoped entity."""

from datetime import datetime
from uuid import UUID, uuid7

from sqlmodel import Field, SQLModel

from src.app.models.base import utc_now


class Project(SQLModel, table=True):
    """Project entity stored in tenant schema.

    Note: No schema= argument in __table_args__ - relies on search_path
    set by TenantDBSession for schema isolation.
    """

    __tablename__ = "projects"

    id: UUID = Field(default_factory=uuid7, primary_key=True)
    name: str = Field(max_length=200, index=True)
    description: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
