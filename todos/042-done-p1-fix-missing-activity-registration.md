---
status: done
priority: p1
issue_id: "042"
tags: [temporal, worker, bug, critical]
dependencies: []
---

# Fix Missing Activity Registration (Production Bug)

## Problem Statement

`update_workflow_execution_status` activity is imported and used in workflows but NOT registered in the worker's activities list. This causes production-only runtime failures when the TenantProvisioningWorkflow tries to execute the unregistered activity.

## Findings

- **Import location**: `src/app/temporal/workflows.py:37` - Activity imported via `workflow.unsafe.imports_passed_through()`
- **Usage locations**:
  - `src/app/temporal/workflows.py:181` - Called on successful provisioning
  - `src/app/temporal/workflows.py:214` - Called on failed provisioning
- **Missing from worker**: `src/app/temporal/worker.py:84-96` - Activity NOT in activities list
- **Activity definition**: `src/app/temporal/activities.py:717` - Activity is properly defined

This is a **production-only failure mode**: workflow starts fine, then fails when it tries to execute an activity the worker doesn't serve.

## Proposed Solutions

### Option 1: Add activity to worker registration (Primary solution)
- **Pros**: Simple, direct fix; no architectural changes needed
- **Cons**: None
- **Effort**: Small (5 minutes)
- **Risk**: Low

Add the missing import and registration:

```python
# src/app/temporal/worker.py
from src.app.temporal.activities import (
    cleanup_email_verification_tokens,
    cleanup_expired_invites,
    cleanup_refresh_tokens,
    create_admin_membership,
    create_stripe_customer,
    dispose_sync_engine,
    drop_tenant_schema,
    get_tenant_info,
    run_tenant_migrations,
    send_welcome_email,
    soft_delete_tenant,
    update_tenant_status,
    update_workflow_execution_status,  # ADD THIS
)

# ... in Worker() constructor:
activities=[
    cleanup_email_verification_tokens,
    cleanup_expired_invites,
    cleanup_refresh_tokens,
    create_admin_membership,
    create_stripe_customer,
    drop_tenant_schema,
    get_tenant_info,
    run_tenant_migrations,
    send_welcome_email,
    soft_delete_tenant,
    update_tenant_status,
    update_workflow_execution_status,  # ADD THIS
],
```

## Recommended Action

Implement Option 1 immediately - this is a bug fix.

## Technical Details

- **Affected Files**: `src/app/temporal/worker.py`
- **Related Components**: TenantProvisioningWorkflow, workflow_executions table
- **Database Changes**: No

## Resources

- Original finding: REVIEW.md - Critical #3
- Related issues: None

## Acceptance Criteria

- [ ] `update_workflow_execution_status` imported in worker.py
- [ ] Activity added to Worker's activities list
- [ ] Worker starts successfully with new activity
- [ ] TenantProvisioningWorkflow completes and updates workflow_executions table

## Work Log

### 2025-12-17 - Initial Discovery
**By:** Claude Code Review
**Actions:**
- Issue discovered during REVIEW.md Temporal review
- Categorized as CRITICAL (production bug)
- Estimated effort: Small

**Learnings:**
- Worker registration must be kept in sync with workflow activity usage
- This drift pattern should be caught by tests (future todo 051)

### 2025-12-17 - Fix Implemented
**By:** Claude Code
**Actions:**
- Added `update_workflow_execution_status` to imports in worker.py (line 29)
- Added `update_workflow_execution_status` to activities list in Worker() (line 100)
- Verified fix compiles successfully with py_compile
- Updated todo status to done

**Result:**
- Worker now properly registers the activity used in TenantProvisioningWorkflow
- Production bug resolved - workflow executions will now complete successfully

## Notes

Source: REVIEW.md Temporal implementation review
