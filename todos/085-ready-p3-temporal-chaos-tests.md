---
status: ready
priority: p3
issue_id: "085"
tags: [testing, temporal, chaos, reliability]
dependencies: []
---

# Missing Chaos Tests for Temporal Workflows

## Problem Statement
Workflows claim idempotency but aren't tested with simulated failures at each step. No verification that compensation (rollback) executes correctly when activities fail.

## Findings
- Location: Tests directory - missing tests
- Tenant provisioning has multiple steps
- No failure injection tests exist
- Compensation logic untested
- Idempotency claims unverified

## Proposed Solutions

### Option 1: Add chaos tests with failure injection
- **Pros**: Verifies reliability guarantees, catches edge cases
- **Cons**: More complex test setup
- **Effort**: Medium
- **Risk**: Low

```python
import pytest
from unittest.mock import patch, AsyncMock
from temporalio.testing import WorkflowEnvironment

@pytest.mark.integration
class TestTenantProvisioningChaos:
    """Chaos tests for tenant provisioning workflow."""

    async def test_failure_at_schema_creation_triggers_cleanup(
        self,
        workflow_environment: WorkflowEnvironment,
    ):
        """Test that schema creation failure doesn't leave orphaned resources."""
        async with workflow_environment as env:
            # Inject failure at schema creation step
            with patch(
                "src.app.temporal.activities.tenant.create_tenant_schema",
                side_effect=Exception("Simulated schema creation failure")
            ):
                result = await env.client.execute_workflow(
                    TenantProvisioningWorkflow.run,
                    args=["test-tenant-id", "test-user-id"],
                    id="test-workflow",
                    task_queue="test-queue",
                )

            # Verify tenant marked as FAILED
            # Verify no orphaned schema exists
            # Verify cleanup activities executed

    async def test_failure_at_membership_triggers_schema_rollback(
        self,
        workflow_environment: WorkflowEnvironment,
    ):
        """Test that membership failure rolls back schema."""
        # Schema created successfully, membership fails
        # Verify schema is dropped in compensation

    async def test_workflow_retries_transient_failures(
        self,
        workflow_environment: WorkflowEnvironment,
    ):
        """Test that transient failures are retried."""
        # First attempt fails, second succeeds
        # Verify workflow completes successfully
```

## Recommended Action
Add chaos test suite for tenant provisioning workflow covering failure at each step.

## Technical Details
- **Affected Files**: New `tests/integration/test_temporal_chaos.py`
- **Related Components**: Temporal workflows, activities
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- Temporal testing docs: https://docs.temporal.io/develop/python/testing-suite

## Acceptance Criteria
- [ ] Chaos tests for each workflow step
- [ ] Failure injection at schema creation
- [ ] Failure injection at membership creation
- [ ] Compensation verification
- [ ] Transient failure retry verification
- [ ] Tests pass reliably
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Workflow reliability claims must be tested
- Chaos testing catches edge cases happy-path tests miss

## Notes
Source: Triage session on 2025-12-18
