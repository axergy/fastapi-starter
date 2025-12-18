"""Project schemas for API request/response."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    """Schema for creating a project."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Project name cannot be empty or whitespace only")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Project name cannot be empty or whitespace only")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class ProjectRead(BaseModel):
    """Schema for reading a project."""

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
