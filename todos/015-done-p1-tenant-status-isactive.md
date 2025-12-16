---
id: "015"
title: "Tenant Status is_active Not Updated"
status: pending
priority: p1
source: "REVIEW.md - HIGH #7"
category: correctness
---

# Tenant Status is_active Not Updated

## Problem

`update_tenant_status` activity only updates the `status` field, not the `is_active` flag. Failed or deleted tenants remain `is_active=True` and appear valid to the system.

## Risk

- **Security**: Failed tenants still accessible via is_active checks
- **Data integrity**: Inconsistent tenant state
- **User confusion**: "Failed" tenant appears active

## Verified Findings

| Location | Line | Issue |
|----------|------|-------|
| `src/app/temporal/activities.py` | 273-292 | `update_tenant_status` activity |
| `src/app/temporal/activities.py` | 290 | Only sets `tenant.status = status` |
| `src/app/temporal/activities.py` | - | Does NOT set `is_active` based on status |

### Current Code (Problem)

```python
@activity.defn
async def update_tenant_status(tenant_id: str, status: str) -> bool:
    async with get_session_context() as session:
        tenant = await session.get(Tenant, UUID(tenant_id))
        if tenant:
            tenant.status = status  # Only updates status
            # Missing: is_active update based on status!
            await session.commit()
            return True
    return False
```

## Fix

Update `is_active` based on status:
- `status="ready"` → `is_active=True`
- `status="failed"` → `is_active=False`
- `status="deleted"` → `is_active=False`

### Code Changes

```python
@activity.defn
async def update_tenant_status(tenant_id: str, status: str) -> bool:
    async with get_session_context() as session:
        tenant = await session.get(Tenant, UUID(tenant_id))
        if tenant:
            tenant.status = status
            # Update is_active based on terminal status
            if status == "ready":
                tenant.is_active = True
            elif status in ("failed", "deleted"):
                tenant.is_active = False
            await session.commit()
            return True
    return False
```

## Files to Modify

- `src/app/temporal/activities.py`

## Acceptance Criteria

- [ ] `is_active=True` when status becomes "ready"
- [ ] `is_active=False` when status becomes "failed" or "deleted"
- [ ] Unit test verifies is_active updates with status changes
- [ ] Document the status-to-is_active mapping
