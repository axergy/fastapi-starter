---
status: pending
priority: p1
issue_id: "026"
tags: [dry, validation, constants]
dependencies: []
---

# Centralize Slug Validation Constants

## Problem Statement
Slug regex and "56" max length are duplicated across multiple files. The slug validation rules should have a single source of truth in validators.py.

## Findings
- `src/app/schemas/auth.py` line 77: Hardcoded regex `^[a-z][a-z0-9]*(_[a-z0-9]+)*$`
- `src/app/schemas/tenant.py` line 22: Same hardcoded regex (duplicate)
- `src/app/schemas/auth.py` line 43: Hardcoded `max_length=56`
- `src/app/schemas/tenant.py` line 12: Hardcoded `max_length=56`
- `src/app/models/public/tenant.py` line 13: Computes `MAX_SLUG_LENGTH = MAX_SCHEMA_LENGTH - len("tenant_")`
- `src/app/models/public/tenant.py` line 41: Hardcoded `f"tenant_{self.slug}"` prefix
- `src/app/core/security/validators.py` line 5: Only has `MAX_SCHEMA_LENGTH = 63`
- Missing from validators.py: `MAX_TENANT_SLUG_LENGTH`, `TENANT_SLUG_REGEX`, `TENANT_SCHEMA_PREFIX`

## Proposed Solutions

### Option 1: Centralize all constants in validators.py
- **Pros**: Single source of truth, easier maintenance, consistent validation
- **Cons**: None
- **Effort**: Medium
- **Risk**: Low

## Recommended Action
Add missing constants to validators.py and update all consumers.

## Technical Details
- **Affected Files**:
  - `src/app/core/security/validators.py` - Add constants and `validate_tenant_slug_format()` function
  - `src/app/schemas/auth.py` - Use shared constants and validator
  - `src/app/schemas/tenant.py` - Use shared constants and validator
  - `src/app/models/public/tenant.py` - Use `TENANT_SCHEMA_PREFIX` constant
- **Related Components**: Slug validation across the application
- **Database Changes**: No

## Resources
- Original finding: REVIEW.md - High #5
- Related issues: #030 (cleanup utils), #033 (property tests)

## Acceptance Criteria
- [ ] validators.py has: `MAX_TENANT_SLUG_LENGTH`, `TENANT_SLUG_REGEX`, `TENANT_SCHEMA_PREFIX`
- [ ] validators.py has `validate_tenant_slug_format()` function
- [ ] auth.py uses `MAX_TENANT_SLUG_LENGTH` and `validate_tenant_slug_format()`
- [ ] tenant.py schema uses `MAX_TENANT_SLUG_LENGTH` and `validate_tenant_slug_format()`
- [ ] tenant.py model uses `TENANT_SCHEMA_PREFIX` for schema_name property
- [ ] No hardcoded "56" or "tenant_" in schema files
- [ ] Tests pass

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P1 (DRY foundation)
- Estimated effort: Medium
- Foundation for Issues 030 and 033

**Learnings:**
- Constants should be defined in validators.py as single source of truth

## Notes
Source: REVIEW.md Round 3 - Code Cleanup

New constants to add:
```python
MAX_SCHEMA_LENGTH: Final[int] = 63  # PostgreSQL identifier limit
TENANT_SCHEMA_PREFIX: Final[str] = "tenant_"
MAX_TENANT_SLUG_LENGTH: Final[int] = MAX_SCHEMA_LENGTH - len(TENANT_SCHEMA_PREFIX)  # 56
TENANT_SLUG_REGEX: Final[str] = r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$"
```
