---
status: ready
priority: p2
issue_id: "010"
tags: [security, validation, data-integrity]
dependencies: []
---

# Missing Input Validation on Tenant Status Updates

## Problem Statement
The `_sync_update_tenant_status` function accepts any string for status without validation. This allows invalid status values to be stored in the database.

## Findings
- No validation that status is a valid TenantStatus enum value
- Location: `src/app/temporal/activities.py:188-201`
- Any string accepted and stored in database
- Application code expecting valid enum values may break

## Proposed Solutions

### Option 1: Add enum validation in activity (RECOMMENDED)
- **Pros**: Simple, immediate validation, clear error
- **Cons**: None
- **Effort**: Small (30 minutes)
- **Risk**: Low

Implementation:
```python
from src.app.models.public import TenantStatus

def _sync_update_tenant_status(tenant_id: str, status: str) -> bool:
    # Validate status is a valid enum value
    try:
        TenantStatus(status)
    except ValueError as e:
        raise ValueError(f"Invalid tenant status: {status}") from e

    engine = get_sync_engine()
    with Session(engine) as session:
        tenant_uuid = UUID(tenant_id)
        stmt = select(Tenant).where(Tenant.id == tenant_uuid)
        tenant = session.scalars(stmt).first()

        if not tenant:
            return False

        tenant.status = status
        session.commit()
        return True
```

### Option 2: Use enum type directly in function signature
- **Pros**: Type safety at call site
- **Cons**: May require caller changes
- **Effort**: Small (1 hour)
- **Risk**: Low

## Recommended Action
Implement Option 1 - add validation at start of function

## Technical Details
- **Affected Files**:
  - `src/app/temporal/activities.py`
- **Related Components**: Tenant provisioning workflow
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Status validated against TenantStatus enum
- [ ] ValueError raised for invalid status
- [ ] Clear error message includes invalid value
- [ ] Tests for validation logic
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 IMPORTANT
- Estimated effort: Small (30 minutes)

**Learnings:**
- Always validate against enums when storing enum-like values
- Defense in depth even for internal function calls

## Notes
Source: Triage session on 2025-12-04
