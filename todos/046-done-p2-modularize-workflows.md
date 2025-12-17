---
status: done
priority: p2
issue_id: "046"
tags: [temporal, refactoring, maintainability]
dependencies: []
---

# Modularize Workflows Structure

## Problem Statement

`workflows.py` is a "god file" with all 4 workflows (416 lines). As workflows grow with signals, updates, and queries, this becomes:
- Hard to navigate and maintain
- Difficult to version individual workflows
- Prone to accidental coupling between workflows
- Challenging for code review

## Findings

- **Current file**: `src/app/temporal/workflows.py` - 416 lines
- **Contains 4 workflows**:
  - `UserOnboardingWorkflow` (lines 42-84)
  - `TenantProvisioningWorkflow` (lines 87-255)
  - `TenantDeletionWorkflow` (lines 258-325)
  - `TokenCleanupWorkflow` (lines 328-416)
- **All share imports** via `workflow.unsafe.imports_passed_through()` block

## Proposed Solutions

### Option 1: Split into modular structure with shared steps (Primary solution)
- **Pros**: Clear boundaries; easier versioning; reusable steps; smaller code reviews
- **Cons**: More files to navigate; import path changes
- **Effort**: Large (3-4 hours)
- **Risk**: Low (pure refactoring, no behavior change)

**Target Structure:**
```
src/app/temporal/
  workflows/
    __init__.py                 # Re-exports all workflows
    user_onboarding.py          # UserOnboardingWorkflow
    tenant_provisioning.py      # TenantProvisioningWorkflow
    tenant_deletion.py          # TenantDeletionWorkflow
    token_cleanup.py            # TokenCleanupWorkflow
    _steps/
      __init__.py               # Re-exports step functions
      common.py                 # DEFAULT_RETRY, activity_opts helpers
      tenant_steps.py           # ensure_schema_provisioned, etc.
```

**Example: workflows/__init__.py**
```python
"""Temporal Workflows - Re-exports for worker registration."""
from src.app.temporal.workflows.tenant_deletion import TenantDeletionWorkflow
from src.app.temporal.workflows.tenant_provisioning import TenantProvisioningWorkflow
from src.app.temporal.workflows.token_cleanup import TokenCleanupWorkflow
from src.app.temporal.workflows.user_onboarding import UserOnboardingWorkflow

__all__ = [
    "TenantDeletionWorkflow",
    "TenantProvisioningWorkflow",
    "TokenCleanupWorkflow",
    "UserOnboardingWorkflow",
]
```

**Example: workflows/_steps/common.py**
```python
"""Shared workflow step utilities."""
from datetime import timedelta
from temporalio.common import RetryPolicy

DEFAULT_RETRY = RetryPolicy(
    maximum_attempts=5,
    initial_interval=timedelta(seconds=1),
)

def short_activity_opts():
    """Options for quick activities (DB reads, status updates)."""
    return dict(
        start_to_close_timeout=timedelta(seconds=30),
        retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=1)),
    )

def medium_activity_opts():
    """Options for medium activities (external API calls)."""
    return dict(
        start_to_close_timeout=timedelta(seconds=60),
        retry_policy=DEFAULT_RETRY,
    )

def long_activity_opts():
    """Options for long activities (migrations, schema operations)."""
    return dict(
        start_to_close_timeout=timedelta(minutes=10),
        retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=2)),
    )
```

**Example: workflows/tenant_provisioning.py**
```python
"""Tenant Provisioning Workflow."""
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.app.models.public import TenantStatus
    from src.app.temporal.activities import (
        # ... activity imports
    )


@workflow.defn
class TenantProvisioningWorkflow:
    """Provision a new tenant with Saga-pattern compensation."""

    @workflow.run
    async def run(self, tenant_id: str, user_id: str | None = None) -> str:
        # ... same implementation, moved here
```

## Recommended Action

Implement Option 1 - split workflows into individual modules with shared steps.

## Technical Details

- **Files to create**:
  - `src/app/temporal/workflows/__init__.py`
  - `src/app/temporal/workflows/user_onboarding.py`
  - `src/app/temporal/workflows/tenant_provisioning.py`
  - `src/app/temporal/workflows/tenant_deletion.py`
  - `src/app/temporal/workflows/token_cleanup.py`
  - `src/app/temporal/workflows/_steps/__init__.py`
  - `src/app/temporal/workflows/_steps/common.py`
  - `src/app/temporal/workflows/_steps/tenant_steps.py`
- **Files to delete**: `src/app/temporal/workflows.py` (after migration)
- **Files to update**: `src/app/temporal/worker.py` (import path)
- **Related Components**: worker.py, any workflow start sites
- **Database Changes**: No

## Resources

- Original finding: REVIEW.md - High #4
- Python SDK patterns: workflow.defn decorator per file

## Acceptance Criteria

- [x] All 4 workflows moved to individual files
- [x] `__init__.py` re-exports all workflows for worker registration
- [x] Common step utilities extracted to `_steps/common.py`
- [x] Worker imports updated to use new paths (backward compatible via __init__.py)
- [x] Old `workflows.py` deleted
- [x] All files compile successfully with py_compile

## Work Log

### 2025-12-17 - Refactoring Complete
**By:** Claude Code
**Actions:**
- Created modular workflows structure with separate files for each workflow
- Created `_steps/common.py` with shared retry policies and helper functions
- Moved UserOnboardingWorkflow to `user_onboarding.py`
- Moved TenantProvisioningWorkflow to `tenant_provisioning.py`
- Moved TenantDeletionWorkflow to `tenant_deletion.py`
- Moved TokenCleanupWorkflow to `token_cleanup.py`
- Created `workflows/__init__.py` with re-exports for backward compatibility
- Deleted old `workflows.py` file
- Verified all files compile successfully

**Results:**
- 416-line god file split into 4 focused workflow modules
- Each workflow has its own `workflow.unsafe.imports_passed_through()` block
- Import paths remain backward compatible via __init__.py re-exports
- All existing imports in worker.py and service files continue to work unchanged

### 2025-12-17 - Initial Discovery
**By:** Claude Code Review
**Actions:**
- Issue discovered during REVIEW.md Temporal review
- Categorized as HIGH (maintainability)
- Estimated effort: Large

**Learnings:**
- Keep workflow.defn classes focused and small
- Shared retry policies reduce duplication
- Steps can be extracted for reuse across workflows

## Notes

Source: REVIEW.md Temporal implementation review

Migration note: Import paths change from `src.app.temporal.workflows` to `src.app.temporal.workflows.tenant_provisioning` etc. The `__init__.py` re-export maintains backward compatibility.
