---
id: "016"
title: "Workflow Execution Status Updates"
status: pending
priority: p1
source: "REVIEW.md - HIGH #6"
category: correctness
---

# Workflow Execution Status Updates

## Problem

`TenantProvisioningWorkflow` doesn't update the `workflow_executions` table status. The record is created with "running" status but never updated to "completed" or "failed".

## Risk

- **Lost observability**: Can't track workflow completion status
- **Stale data**: All workflows show "running" forever
- **Debugging difficulty**: Can't distinguish completed vs stuck workflows

## Verified Findings

| Location | Line | Issue |
|----------|------|-------|
| `src/app/services/tenant_service.py` | 84-87 | Creates workflow_execution with "running" status |
| `src/app/temporal/workflows.py` | 167-195 | Workflow does NOT update workflow_executions |
| `src/app/temporal/workflows.py` | - | Only tenant.status is updated via activities |

### Current Flow

```
1. tenant_service.py creates WorkflowExecution(status="running") ✓
2. Workflow runs...
3. Workflow completes or fails
4. workflow_executions.status still "running" ✗
```

## Fix

Add activity to update workflow_execution status and call it at workflow completion/failure.

### Code Changes

**New Activity (activities.py):**
```python
@activity.defn
async def update_workflow_execution_status(workflow_id: str, status: str, error_message: str | None = None) -> bool:
    """Update workflow_executions table with final status."""
    async with get_session_context() as session:
        result = await session.execute(
            select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow_id)
        )
        execution = result.scalar_one_or_none()
        if execution:
            execution.status = status
            if error_message:
                execution.error_message = error_message
            execution.completed_at = datetime.utcnow() if status in ("completed", "failed") else None
            await session.commit()
            return True
    return False
```

**Workflow Update (workflows.py):**
```python
@workflow.defn
class TenantProvisioningWorkflow:
    @workflow.run
    async def run(self, input: TenantProvisioningInput) -> TenantProvisioningResult:
        try:
            # ... existing workflow logic ...

            # Update workflow execution to completed
            await workflow.execute_activity(
                update_workflow_execution_status,
                args=[workflow.info().workflow_id, "completed", None],
                ...
            )
            return result
        except Exception as e:
            # Update workflow execution to failed
            await workflow.execute_activity(
                update_workflow_execution_status,
                args=[workflow.info().workflow_id, "failed", str(e)],
                ...
            )
            raise
```

## Files to Modify

- `src/app/temporal/activities.py` (add update_workflow_execution_status)
- `src/app/temporal/workflows.py` (call activity on completion/failure)
- `src/app/models/public/workflow.py` (may need completed_at, error_message fields)

## Acceptance Criteria

- [ ] New `update_workflow_execution_status` activity created
- [ ] Workflow calls activity on successful completion (status="completed")
- [ ] Workflow calls activity on failure (status="failed", error_message set)
- [ ] WorkflowExecution model has completed_at and error_message fields
- [ ] Integration test verifies status updates through workflow lifecycle
