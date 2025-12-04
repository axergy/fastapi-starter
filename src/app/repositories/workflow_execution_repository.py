"""Repository for WorkflowExecution entity."""

from uuid import UUID

from sqlmodel import select

from src.app.models.public import WorkflowExecution
from src.app.repositories.base import BaseRepository


class WorkflowExecutionRepository(BaseRepository[WorkflowExecution]):
    """Repository for WorkflowExecution entity in public schema."""

    model = WorkflowExecution

    async def get_by_workflow_id(self, workflow_id: str) -> WorkflowExecution | None:
        """Get workflow execution by workflow_id."""
        result = await self.session.execute(
            select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow_id)
        )
        return result.scalar_one_or_none()

    async def list_by_entity(
        self, entity_type: str, entity_id: UUID
    ) -> list[WorkflowExecution]:
        """List workflow executions for a specific entity."""
        result = await self.session.execute(
            select(WorkflowExecution)
            .where(
                WorkflowExecution.entity_type == entity_type,
                WorkflowExecution.entity_id == entity_id,
            )
            .order_by(WorkflowExecution.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_status(self, status: str) -> list[WorkflowExecution]:
        """List workflow executions by status."""
        result = await self.session.execute(
            select(WorkflowExecution)
            .where(WorkflowExecution.status == status)
            .order_by(WorkflowExecution.created_at.desc())
        )
        return list(result.scalars().all())
