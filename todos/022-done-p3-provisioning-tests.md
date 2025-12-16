---
id: "022"
title: "Provisioning Lifecycle Integration Tests"
status: pending
priority: p3
source: "REVIEW.md - MEDIUM #12"
category: testing
---

# Provisioning Lifecycle Integration Tests

## Problem

Missing integration tests for full tenant provisioning lifecycle. Current tests verify workflow_id is returned but don't test the complete state machine transitions.

## Risk

- **Untested state transitions**: pending → running → ready not verified
- **Failure path untested**: failed state not tested
- **is_active inconsistency**: Not verified that is_active matches status
- **Regression risk**: Future changes may break lifecycle

## Verified Findings

| Location | Line | Issue |
|----------|------|-------|
| `tests/integration/test_auth.py` | 44 | Verifies workflow_id returned |
| - | - | Missing: Assert workflow_executions row created |
| - | - | Missing: Test provisioning → ready transition |
| - | - | Missing: Test failure path → status=failed, is_active=false |

### Current Test Coverage

```python
# Only tests initial creation
def test_register_creates_user_and_tenant():
    response = client.post("/auth/register", ...)
    assert response.json()["workflow_id"]  # Just checks ID returned
    # Missing: verify workflow_executions table
    # Missing: verify state transitions
```

## Fix

Add comprehensive integration tests for:
1. Success path: pending → running → ready (is_active=true)
2. Failure path: pending → running → failed (is_active=false)
3. workflow_executions table updates

### Test Cases to Add

```python
class TestProvisioningLifecycle:
    async def test_success_path_creates_workflow_execution(self, db):
        """Verify workflow_execution record created on registration."""
        response = client.post("/auth/register", json={...})
        workflow_id = response.json()["workflow_id"]

        # Verify workflow_execution exists
        execution = await db.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.workflow_id == workflow_id
            )
        )
        assert execution.scalar_one() is not None

    async def test_success_path_updates_tenant_status(self, db, mock_temporal):
        """Verify tenant transitions to ready with is_active=true."""
        # Register tenant
        # Simulate workflow completion
        # Assert tenant.status == "ready"
        # Assert tenant.is_active == True

    async def test_failure_path_marks_tenant_inactive(self, db, mock_temporal):
        """Verify failed provisioning sets is_active=false."""
        # Register tenant
        # Simulate workflow failure
        # Assert tenant.status == "failed"
        # Assert tenant.is_active == False

    async def test_workflow_execution_status_updated(self, db, mock_temporal):
        """Verify workflow_executions.status reflects workflow state."""
        # Register tenant (creates "running" execution)
        # Simulate workflow completion
        # Assert execution.status == "completed"
```

## Files to Modify

- `tests/integration/test_auth.py` or new `tests/integration/test_provisioning.py`

## Acceptance Criteria

- [ ] Test verifies workflow_execution record created
- [ ] Test verifies success path: status=ready, is_active=true
- [ ] Test verifies failure path: status=failed, is_active=false
- [ ] Test verifies workflow_executions.status updates
- [ ] Tests can mock Temporal or use test worker
