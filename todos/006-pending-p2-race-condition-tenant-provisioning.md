---
status: ready
priority: p2
issue_id: "006"
tags: [data-integrity, race-condition, multi-tenancy, temporal]
dependencies: []
---

# Race Condition in Tenant Provisioning

## Problem Statement
There's a TOCTOU (Time-of-Check-Time-of-Use) race condition in tenant creation. Between checking if a slug exists and starting the workflow, another request could create a tenant with the same slug.

## Findings
- Existence check and workflow start are not atomic
- Location: `src/app/services/tenant_service.py:40-54`
- Concurrent requests can pass existence check simultaneously
- Results in duplicate tenant creation attempts or workflow failures

## Proposed Solutions

### Option 1: Create tenant record first with DB constraint (RECOMMENDED)
- **Pros**: Atomic, leverages database guarantees, clean error handling
- **Cons**: Requires workflow modification to accept tenant_id
- **Effort**: Medium (3-4 hours)
- **Risk**: Low

Implementation:
```python
async def create_tenant(self, name: str, slug: str) -> str:
    # Create tenant record FIRST (unique constraint on slug)
    try:
        tenant = Tenant(name=name, slug=slug, status=TenantStatus.PROVISIONING.value)
        self.tenant_repo.add(tenant)
        await self.session.commit()
    except IntegrityError:
        await self.session.rollback()
        raise ValueError(f"Tenant with slug '{slug}' already exists")

    # Start workflow with tenant_id
    workflow_id = self.get_workflow_id(slug)
    await client.start_workflow(
        TenantProvisioningWorkflow.run,
        args=[str(tenant.id)],  # Pass tenant_id instead
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )
    return workflow_id
```

### Option 2: Use distributed lock (Redis/database advisory lock)
- **Pros**: Works without workflow changes
- **Cons**: Adds complexity, external dependency
- **Effort**: Medium (4-5 hours)
- **Risk**: Medium

## Recommended Action
Implement Option 1 - database-first approach with unique constraint

## Technical Details
- **Affected Files**:
  - `src/app/services/tenant_service.py`
  - `src/app/temporal/workflows.py`
  - `src/app/temporal/activities.py`
- **Related Components**: Tenant provisioning workflow, registration flow
- **Database Changes**: No (unique constraint already exists on slug)

## Resources
- Original finding: Code review triage session
- TOCTOU: https://en.wikipedia.org/wiki/Time-of-check_to_time-of-use

## Acceptance Criteria
- [ ] Tenant record created before workflow starts
- [ ] IntegrityError caught and converted to user-friendly error
- [ ] Workflow updated to accept tenant_id instead of creating tenant
- [ ] Registration flow updated accordingly
- [ ] Tests for concurrent registration attempts
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 IMPORTANT
- Estimated effort: Medium (3-4 hours)

**Learnings:**
- Database constraints are the ultimate source of truth for uniqueness
- Check-then-act patterns are inherently racy without locks

## Notes
Source: Triage session on 2025-12-04
