---
status: ready
priority: p3
issue_id: "081"
tags: [architecture, temporal, versioning, deployment]
dependencies: []
---

# Temporal Workflow Missing Versioning

## Problem Statement
Workflows don't use Temporal's workflow versioning feature. If you need to change workflow logic, all in-flight workflows will fail or behave unpredictably.

## Findings
- Location: `src/app/temporal/workflows/tenant_provisioning.py`
- No `workflow.get_version()` calls
- Workflow logic changes break in-flight executions
- Non-determinism errors on deployment
- Risk of stuck workflows

## Proposed Solutions

### Option 1: Implement workflow versioning
- **Pros**: Safe deployments, backward compatibility, graceful migration
- **Cons**: Slightly more complex workflow code
- **Effort**: Medium
- **Risk**: Low

```python
from temporalio import workflow

@workflow.defn
class TenantProvisioningWorkflow:
    @workflow.run
    async def run(self, tenant_id: str, user_id: str | None = None) -> str:
        # Version 1: Original implementation
        # Version 2: Added retry logic for schema creation
        version = workflow.get_version(
            "tenant-provisioning-v2",
            workflow.DEFAULT_VERSION,  # min version
            2  # max version
        )

        if version == workflow.DEFAULT_VERSION:
            # Original logic for in-flight workflows
            await self._provision_v1(tenant_id, user_id)
        else:
            # New logic for new workflows
            await self._provision_v2(tenant_id, user_id)

        return f"Tenant {tenant_id} provisioned"

    async def _provision_v1(self, tenant_id: str, user_id: str | None):
        # Original implementation
        pass

    async def _provision_v2(self, tenant_id: str, user_id: str | None):
        # New implementation with improvements
        pass
```

## Recommended Action
Add versioning to tenant provisioning workflow and document versioning strategy for future workflows.

## Technical Details
- **Affected Files**: `src/app/temporal/workflows/tenant_provisioning.py`
- **Related Components**: Temporal workers, deployment process
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- Temporal versioning docs: https://docs.temporal.io/workflows#workflow-versioning

## Acceptance Criteria
- [ ] Workflow versioning implemented
- [ ] Current logic preserved as version 1
- [ ] Documentation for adding future versions
- [ ] Safe deployment tested
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Temporal workflows must be deterministic
- Versioning enables safe evolution of workflow logic

## Notes
Source: Triage session on 2025-12-18
