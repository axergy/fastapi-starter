---
status: pending
priority: p1
issue_id: "028"
tags: [tests, cleanup, dead-code]
dependencies: []
---

# Delete xfail Test with Todo Reference

## Problem Statement
The xfail test in test_provisioning.py references a todo file path, creating coupling between tests and external documentation. This is template noise that documents unimplemented behavior and will rot over time.

## Findings
- `tests/integration/test_provisioning.py` lines 19-23: `@pytest.mark.xfail` decorator
- Reason string references: `todos/016-done-p1-workflow-execution-observability.md`
- Test `test_registration_creates_workflow_execution` documents expected behavior that doesn't exist
- Lines 65-70: Similar todo reference in assertion message
- Lines 120-125: Comment block about future Temporal test infrastructure

## Proposed Solutions

### Option 1: Delete xfail test and simplify comments
- **Pros**: Removes template noise, cleaner test file
- **Cons**: Loses documentation of expected behavior
- **Effort**: Small
- **Risk**: Low

## Recommended Action
Delete the xfail test entirely and simplify comments in remaining tests.

## Technical Details
- **Affected Files**:
  - `tests/integration/test_provisioning.py`
- **Related Components**: Integration test suite
- **Database Changes**: No

## Resources
- Original finding: REVIEW.md - Critical #3
- Related issues: None

## Acceptance Criteria
- [ ] `test_registration_creates_workflow_execution` test deleted
- [ ] No references to todo files in test code
- [ ] Comment in `test_tenant_transitions_to_ready` simplified to neutral explanation
- [ ] Tests pass

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P1 (template cleanup)
- Estimated effort: Small

**Learnings:**
- xfail tests documenting unimplemented features are template noise

## Notes
Source: REVIEW.md Round 3 - Code Cleanup

Replace comment:
```python
# Before
# NOTE: To test the full transition to "ready" status, we would need to:
# 1. Either use a real Temporal worker (integration test), OR
# 2. Directly call the workflow completion activity
# For now, this test verifies the initial provisioning state.
# Full workflow integration testing should be added when Temporal test
# infrastructure is set up.

# After
# This test intentionally verifies the *initial* provisioning state because
# Temporal is mocked in this suite.
```
