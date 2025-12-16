---
status: done
priority: p1
issue_id: "006"
tags: [temporal, workflows, race-condition, api]
dependencies: []
---

# Tenant Deletion Order Race Condition

## Problem Statement
`TenantDeletionWorkflow` drops the tenant schema BEFORE soft-deleting the tenant record. During this window, API requests can still be routed to the tenant (validation passes), but queries fail with 500 errors because the schema no longer exists.

## Findings
- `src/app/temporal/workflows.py`: TenantDeletionWorkflow order:
  1. `get_tenant_info` - get schema name
  2. `drop_tenant_schema` - DROP SCHEMA CASCADE
  3. `soft_delete_tenant` - set is_active=False, deleted_at=now()
- `src/app/api/dependencies/tenant.py:24-50`: `get_validated_tenant()` checks:
  - `tenant is None` -> 404
  - `not tenant.is_active` -> 403
  - `tenant.status != READY` -> 503
  - **NO check for `deleted_at`**

**Race Condition Timeline:**
```
T0:      Deletion workflow: DROP SCHEMA tenant_acme CASCADE
T0+500ms: Request arrives for tenant "acme-corp"
T0+500ms: get_validated_tenant() checks tenant record
          - tenant.deleted_at is STILL NULL (soft-delete hasn't happened)
          - tenant.is_active is STILL TRUE
          - tenant.status is STILL "ready"
          - Validation PASSES
T0+501ms: Route handler tries to access tenant schema
          - Session tries to SET search_path TO tenant_acme
          - Schema doesn't exist (was dropped)
          - 500 Internal Server Error

T0+1s:   Deletion workflow: soft_delete_tenant() sets is_active=False
         (Too late - user already got 500 error)
```

## Proposed Solutions

### Option 1: Soft-Delete First, Then Drop Schema (Recommended)
- **Pros**: Immediate 403 response, no 500 errors, clean user experience
- **Cons**: None
- **Effort**: Small
- **Risk**: Low

**Implementation:**

1. **Reorder workflow steps:**
```python
# src/app/temporal/workflows.py - TenantDeletionWorkflow

@workflow.run
async def run(self, tenant_id: str) -> dict[str, bool | str]:
    # Step 1: Soft-delete tenant record FIRST
    # This stops new API requests immediately with graceful 403
    await workflow.execute_activity(
        soft_delete_tenant,
        SoftDeleteTenantInput(tenant_id=tenant_id),
        start_to_close_timeout=timedelta(seconds=10),
        retry_policy=RetryPolicy(...),
    )

    # Step 2: Get tenant info (need schema name)
    tenant_info = await workflow.execute_activity(
        get_tenant_info,
        GetTenantInput(tenant_id=tenant_id),
        # ...
    )

    # Step 3: Drop tenant schema (now safe - no requests can reach it)
    await workflow.execute_activity(
        drop_tenant_schema,
        DropSchemaInput(schema_name=tenant_info.schema_name),
        # ...
    )

    return {"deleted": True, "tenant_id": tenant_id}
```

2. **Add deleted_at check to validation (defense in depth):**
```python
# src/app/api/dependencies/tenant.py

async def get_validated_tenant(...):
    # ...
    if tenant.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Tenant has been deleted",
        )
    # ...
```

## Recommended Action
Reorder deletion workflow to soft-delete first, and add `deleted_at` check to tenant validation.

## Technical Details
- **Affected Files**:
  - `src/app/temporal/workflows.py`
  - `src/app/api/dependencies/tenant.py`
- **Related Components**: Tenant deletion, API request routing
- **Database Changes**: No

## Resources
- Original finding: Code Review - "Logic: Fix Deletion Order"
- Related issues: None

## Acceptance Criteria
- [ ] `soft_delete_tenant` activity runs BEFORE `drop_tenant_schema`
- [ ] `get_validated_tenant()` checks `deleted_at` field
- [ ] Deleted tenants return 410 Gone (or 403 Forbidden)
- [ ] No 500 errors during tenant deletion window
- [ ] Tests updated for new order
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review analysis
- Categorized as P1 High (user experience, error handling)
- Estimated effort: Small

**Learnings:**
- Distributed operations (workflow + API) need careful ordering
- Soft-delete should be the first step to stop new requests immediately
- Defense in depth: check deleted_at even if is_active should be false

## Notes
Source: Code review analysis on 2025-12-16
