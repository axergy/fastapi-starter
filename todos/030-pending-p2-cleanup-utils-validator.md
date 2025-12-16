---
status: pending
priority: p2
issue_id: "030"
tags: [tests, dry, validation]
dependencies: ["026"]
---

# Cleanup Utils Reuse Schema Validator

## Problem Statement
tests/utils/cleanup.py duplicates schema validation logic that already exists in validators.py. The two implementations use slightly different regex patterns (capturing vs non-capturing groups).

## Findings
- `tests/utils/cleanup.py` lines 13-40: Own regex and validation logic
  - Line 15: `_SCHEMA_NAME_PATTERN = re.compile(r"^tenant_[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")` (non-capturing)
  - Custom validation with length check against hardcoded 63
- `src/app/core/security/validators.py` lines 8-46: Canonical implementation
  - Uses capturing group `(_[a-z0-9]+)*`
  - Has all the same validation logic

## Proposed Solutions

### Option 1: Import and reuse validators.py
- **Pros**: Single source of truth, consistent validation
- **Cons**: None
- **Effort**: Small
- **Risk**: Low

## Recommended Action
Replace custom validation with import from validators.py.

## Technical Details
- **Affected Files**:
  - `tests/utils/cleanup.py`
- **Related Components**: Test utilities, validators
- **Database Changes**: No

## Resources
- Original finding: REVIEW.md - Medium #8
- Related issues: #026 (centralize constants)

## Acceptance Criteria
- [ ] cleanup.py imports `validate_schema_name` from validators.py
- [ ] Local regex and validation logic removed
- [ ] `_validate_schema_name_for_drop` calls canonical validator
- [ ] Tests pass

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P2 (DRY)
- Estimated effort: Small
- Depends on Issue 026

**Learnings:**
- Test utilities should reuse production validators

## Notes
Source: REVIEW.md Round 3 - Code Cleanup

Change:
```python
# Before
_SCHEMA_NAME_PATTERN = re.compile(r"^tenant_[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")

def _validate_schema_name_for_drop(schema_name: str) -> None:
    if len(schema_name) > 63:
        raise ValueError(...)
    if not _SCHEMA_NAME_PATTERN.match(schema_name):
        raise ValueError(...)

# After
from src.app.core.security.validators import validate_schema_name

def _validate_schema_name_for_drop(schema_name: str) -> None:
    validate_schema_name(schema_name)
```
