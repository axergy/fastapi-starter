---
status: pending
priority: p1
issue_id: "027"
tags: [dry, services]
dependencies: []
---

# DRY Workflow ID Generation

## Problem Statement
The workflow_id format string is duplicated in registration_service.py when TenantService.get_workflow_id() already exists as the canonical implementation.

## Findings
- `src/app/services/registration_service.py` line 84: `workflow_id = f"tenant-provision-{tenant_slug}"`
- `src/app/services/tenant_service.py` lines 30-32: Static method `get_workflow_id(slug: str)` that returns `f"tenant-provision-{slug}"`
- The format string is duplicated rather than reusing the existing method
- If format changes, two places need updating

## Proposed Solutions

### Option 1: Use TenantService.get_workflow_id()
- **Pros**: Single source of truth, DRY, future-proof
- **Cons**: None
- **Effort**: Small (one line change)
- **Risk**: Low

## Recommended Action
Replace inline format with `TenantService.get_workflow_id(tenant_slug)`.

## Technical Details
- **Affected Files**:
  - `src/app/services/registration_service.py`
- **Related Components**: Workflow ID generation
- **Database Changes**: No

## Resources
- Original finding: REVIEW.md - High #6
- Related issues: None

## Acceptance Criteria
- [ ] registration_service.py uses `TenantService.get_workflow_id(tenant_slug)`
- [ ] No inline f-string for workflow_id format
- [ ] Tests pass

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P1 (DRY)
- Estimated effort: Small

**Learnings:**
- Even small duplications should be eliminated for consistency

## Notes
Source: REVIEW.md Round 3 - Code Cleanup

Change:
```python
# Before
workflow_id = f"tenant-provision-{tenant_slug}"

# After
workflow_id = TenantService.get_workflow_id(tenant_slug)
```
