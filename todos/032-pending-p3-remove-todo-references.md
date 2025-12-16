---
status: pending
priority: p3
issue_id: "032"
tags: [tests, cleanup, docs]
dependencies: []
---

# Remove "TODO #002" from Test Docstrings

## Problem Statement
Test file references internal tracker "TODO #002" in docstring, which is internal nomenclature that shouldn't appear in production code.

## Findings
- `tests/integration/test_invite_transaction_boundary.py` line 1:
  - `"""Tests for TODO #002: Missing Transaction Boundary in Accept Invite Flow.`
- This references an internal tracker/todo system
- Should be renamed to descriptive test suite name

## Proposed Solutions

### Option 1: Rename to descriptive title
- **Pros**: Clean, self-documenting, no internal tracker leakage
- **Cons**: None
- **Effort**: Small
- **Risk**: Low

## Recommended Action
Rename docstring to "Regression tests: Accept-invite transaction boundary".

## Technical Details
- **Affected Files**:
  - `tests/integration/test_invite_transaction_boundary.py`
- **Related Components**: Test documentation
- **Database Changes**: No

## Resources
- Original finding: REVIEW.md - Polish #10
- Related issues: None

## Acceptance Criteria
- [ ] Docstring renamed to neutral/descriptive title
- [ ] No "TODO #002" or similar tracker references
- [ ] Tests pass

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P3 (polish)
- Estimated effort: Small

**Learnings:**
- Internal tracker references shouldn't leak into production code

## Notes
Source: REVIEW.md Round 3 - Code Cleanup

Change:
```python
# Before
"""Tests for TODO #002: Missing Transaction Boundary in Accept Invite Flow.

# After
"""Regression tests: Accept-invite transaction boundary.
```
