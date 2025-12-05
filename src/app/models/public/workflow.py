"""Workflow execution tracking model."""

from datetime import datetime
from uuid import UUID, uuid7

from sqlmodel import Field, SQLModel

from src.app.models.base import utc_now


class WorkflowExecution(SQLModel, table=True):
    """Workflow execution tracking - links workflows to entities."""

    __tablename__ = "workflow_executions"
    __table_args__ = {"schema": "public"}

    id: UUID = Field(default_factory=uuid7, primary_key=True)
    workflow_id: str = Field(max_length=255, index=True)
    workflow_type: str = Field(max_length=100)
    entity_type: str = Field(max_length=50)  # "tenant", "user"
    entity_id: UUID = Field(index=True)
    status: str = Field(default="pending", max_length=20)  # pending, running, completed, failed
    error_message: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
