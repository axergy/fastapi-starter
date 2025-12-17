"""Workflow execution tracking activities."""

import asyncio
from dataclasses import dataclass

from sqlmodel import Session, select
from temporalio import activity

from src.app.core.db import get_sync_engine
from src.app.models.base import utc_now


@dataclass
class UpdateWorkflowExecutionStatusInput:
    workflow_id: str
    status: str
    error_message: str | None = None


def _sync_update_workflow_execution_status(
    workflow_id: str, status: str, error_message: str | None
) -> bool:
    """Synchronous workflow execution status update logic."""
    from src.app.models.public.workflow import WorkflowExecution

    engine = get_sync_engine()
    with Session(engine) as session:
        stmt = select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow_id)
        execution = session.scalars(stmt).first()

        if not execution:
            return False

        execution.status = status
        if error_message:
            execution.error_message = error_message
        if status in ("completed", "failed"):
            execution.completed_at = utc_now()

        session.commit()
        return True


@activity.defn
async def update_workflow_execution_status(
    input: UpdateWorkflowExecutionStatusInput,
) -> bool:
    """
    Update workflow_executions table with final status.

    Idempotency: Setting a field to a specific value is naturally idempotent.
    If retried, the status will simply be set to the same value again, which
    is a safe no-op. The database will have the correct final state regardless
    of how many times this activity executes.

    Args:
        input: UpdateWorkflowExecutionStatusInput containing workflow_id, status,
            and optional error_message

    Returns:
        True if workflow execution was updated, False if not found
    """
    activity.logger.info(
        f"Updating workflow execution {input.workflow_id} status to: {input.status}"
    )
    result = await asyncio.to_thread(
        _sync_update_workflow_execution_status,
        input.workflow_id,
        input.status,
        input.error_message,
    )

    if not result:
        activity.logger.error(f"Workflow execution {input.workflow_id} not found")
    else:
        activity.logger.info(
            f"Workflow execution {input.workflow_id} status updated to {input.status}"
        )

    return result
