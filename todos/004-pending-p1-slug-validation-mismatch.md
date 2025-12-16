---
status: done
priority: p1
issue_id: "004"
tags: [validation, tenant, api]
dependencies: []
---

# Tenant Slug Validation Mismatch

## Problem Statement
API schema validators allow slugs that DB constraints reject. Slugs like `"0test"` or `"_test"` pass API validation but fail the database CHECK constraint, resulting in 500 errors instead of proper validation errors.

## Findings
- Location: `src/app/schemas/auth.py:70`
  - Regex: `^[a-z0-9_]+$` (allows leading digit or underscore)
- Location: `src/app/schemas/tenant.py:15`
  - Same permissive regex: `^[a-z0-9_]+$`
- Location: Migration `010_add_tenant_slug_length_constraint.py:44`
  - DB constraint regex: `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` (STRICT - must start with letter)
- Location: `src/app/core/security/validators.py:36`
  - Schema name regex requires letter after prefix

**Example failure:**
- Slug `"0acme"` passes API validation
- Creates schema name `"tenant_0acme"`
- Fails DB constraint → 500 error

## Proposed Solutions

### Option 1: Update API validators to match DB constraint
- **Pros**: Proper 422 validation errors, consistent behavior
- **Cons**: More restrictive than before (breaking change for invalid slugs)
- **Effort**: Small
- **Risk**: Low

```python
@field_validator("tenant_slug")
@classmethod
def validate_slug(cls, v: str) -> str:
    if not re.match(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", v):
        raise ValueError(
            "Slug must start with a letter and contain only lowercase "
            "letters, numbers, and single underscores as separators"
        )
    return v
```

## Recommended Action
Update both `auth.py` and `tenant.py` validators to use the stricter regex.

## Technical Details
- **Affected Files**:
  - `src/app/schemas/auth.py`
  - `src/app/schemas/tenant.py`
- **Related Components**: Registration, tenant creation
- **Database Changes**: No (DB constraint already correct)

## Resources
- Original finding: REVIEW.md - IMPORTANT #1
- Related issues: Issue 005 (Slug length mismatch)

## Acceptance Criteria
- [ ] `auth.py` RegisterRequest uses regex `^[a-z][a-z0-9]*(_[a-z0-9]+)*$`
- [ ] `tenant.py` TenantCreate uses same regex
- [ ] Error message explains valid slug format
- [ ] Unit tests for edge cases: `"0test"`, `"_test"`, `"test__double"`, `"test_"`, `"Test"`
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-16 - Resolution
**By:** Claude Code
**Actions:**
- Updated `src/app/schemas/auth.py` line 70 with strict regex pattern
- Updated `src/app/schemas/tenant.py` line 15 with strict regex pattern
- Both validators now use `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` matching DB constraint
- Improved error messages to explain valid slug format
- Marked issue as done

**Changes:**
- Regex now requires slugs to start with a letter
- Single underscores allowed as separators (no consecutive underscores)
- Error message clarifies requirements

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P1 (API Correctness)
- Estimated effort: Small

**Learnings:**
- The DB constraint (migration 010) is the correct source of truth
- API validators should be at least as strict as DB constraints
- Proper error messages improve developer experience

## Notes
Source: REVIEW.md analysis on 2025-12-16
