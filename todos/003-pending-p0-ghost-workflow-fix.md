---
status: pending
priority: p0
issue_id: "003"
tags: [temporal, data-integrity, race-condition, critical]
dependencies: []
---

# Ghost Workflow Race Condition

## Problem Statement
`RegistrationService.register()` starts Temporal workflows BEFORE committing the database transaction. If the workflow activity tries to fetch tenant data before the commit, it fails with "Tenant not found". If the DB commit fails after the workflow starts, the workflow runs against non-existent data.

## Findings
- `src/app/services/registration_service.py:61,71`: `await self.session.flush()` (not commit)
- `src/app/services/registration_service.py:82-87`: `client.start_workflow()` with uncommitted IDs
- `src/app/services/registration_service.py:89`: `await self.session.commit()` AFTER workflow starts
- `src/app/temporal/activities.py:178-192`: `get_tenant_info` activity queries DB for tenant
- If tenant not in DB yet, activity raises `ValueError("Tenant {tenant_id} not found")`

**Race Condition Timeline:**
```
T0:    User created, flushed (ID in memory, not in DB)
T0+1:  Tenant created, flushed (ID in memory, not in DB)
T0+2:  Workflow starts with tenant.id and user.id
T0+3:  Workflow activity queries DB -> "Tenant not found"
T0+4:  Original request commits DB (too late)
```

**Alternate Failure:**
```
T0-T2: Same as above
T0+3:  DB commit fails (uniqueness violation)
T0+4:  Rollback happens, but workflow is already running
T0+5:  Workflow tries to use non-existent tenant
```

## Proposed Solutions

### Option 1: Commit First, Then Start Workflow (Recommended)
- **Pros**: Guarantees tenant exists when workflow runs, clear ordering
- **Cons**: Need to handle workflow start failure separately
- **Effort**: Small
- **Risk**: Low

**Implementation:**
```python
async def register(self, ...) -> tuple[User, str]:
    # Create user and tenant objects
    self.session.add(tenant)

    # 1. COMMIT FIRST (Point of No Return)
    try:
        await self.session.commit()
    except IntegrityError as e:
        await self.session.rollback()
        raise ValueError("Tenant or User already exists") from e

    # 2. Refresh to ensure we have IDs
    await self.session.refresh(user)
    await self.session.refresh(tenant)

    # 3. Start Workflow AFTER commit
    workflow_id = f"tenant-provision-{tenant_slug}"

    try:
        client = await get_temporal_client()
        await client.start_workflow(
            TenantProvisioningWorkflow.run,
            args=[str(tenant.id), str(user.id)],
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )
    except Exception as e:
        # Log error. Do NOT rollback DB. Tenant exists in "provisioning" state.
        # A background sweeper should retry these stuck tenants.
        logger.error(f"Failed to start provisioning workflow for {tenant.id}: {e}")

    return user, workflow_id
```

## Recommended Action
Reorder operations: commit DB first, then start workflow. Handle workflow start failures gracefully.

## Technical Details
- **Affected Files**:
  - `src/app/services/registration_service.py`
  - `src/app/services/tenant_service.py` (verify order is correct - it appears safer)
- **Related Components**: Temporal workflows, tenant provisioning
- **Database Changes**: No

## Resources
- Original finding: Code Review - "Data Integrity ('Ghost Workflows')"
- Related issues: None

## Acceptance Criteria
- [ ] DB commit happens BEFORE workflow start in registration_service.py
- [ ] Workflow start failure doesn't rollback the committed tenant
- [ ] Error is logged for failed workflow starts
- [ ] tenant_service.py verified to have correct order
- [ ] Tests updated to verify ordering
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review analysis
- Categorized as P0 Critical (data integrity risk)
- Estimated effort: Small

**Learnings:**
- External system calls (Temporal) should happen AFTER local state is durable
- flush() gives you IDs but doesn't make them visible to other connections
- Consider background job to retry stuck "provisioning" tenants

## Notes
Source: Code review analysis on 2025-12-16
