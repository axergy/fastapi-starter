---
status: ready
priority: p2
issue_id: "073"
tags: [data-integrity, state-machine, temporal, tenant]
dependencies: []
---

# Missing Validation on Tenant Status Transitions

## Problem Statement
The `update_tenant_status` activity accepts any valid status without checking valid transitions. This allows invalid state transitions like `READY` → `PROVISIONING` or `FAILED` → `READY` without proper cleanup.

## Findings
- Location: `src/app/temporal/activities/tenant.py:88-112`
- Direct status assignment: `tenant.status = status`
- No validation of current → new state transition
- Invalid transitions could cause data corruption
- No audit trail of state changes

## Proposed Solutions

### Option 1: Implement state machine validation
- **Pros**: Prevents invalid transitions, self-documenting
- **Cons**: Minor code addition
- **Effort**: Small
- **Risk**: Low

```python
from enum import Enum

VALID_TRANSITIONS: dict[TenantStatus, set[TenantStatus]] = {
    TenantStatus.PROVISIONING: {TenantStatus.READY, TenantStatus.FAILED},
    TenantStatus.READY: set(),  # Terminal state (except soft delete)
    TenantStatus.FAILED: {TenantStatus.PROVISIONING},  # Allow retry
}

def validate_status_transition(current: str, new: str) -> bool:
    """Validate tenant status transition is allowed."""
    try:
        current_enum = TenantStatus(current)
        new_enum = TenantStatus(new)
    except ValueError:
        return False

    allowed = VALID_TRANSITIONS.get(current_enum, set())
    return new_enum in allowed

# In activity:
if not validate_status_transition(tenant.status, status):
    raise ValueError(
        f"Invalid status transition: {tenant.status} → {status}"
    )
```

## Recommended Action
Implement state machine validation in tenant status update activity.

## Technical Details
- **Affected Files**: `src/app/temporal/activities/tenant.py`, possibly new `src/app/core/state_machine.py`
- **Related Components**: Tenant provisioning workflow
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] State transition map defined
- [ ] Validation function implemented
- [ ] Invalid transitions raise clear error
- [ ] Tests for valid and invalid transitions
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- State machines should be explicit and validated
- Implicit state changes lead to hard-to-debug issues

## Notes
Source: Triage session on 2025-12-18
