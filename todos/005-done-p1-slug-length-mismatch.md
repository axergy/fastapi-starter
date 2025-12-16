---
status: done
priority: p1
issue_id: "005"
tags: [validation, tenant, schema]
dependencies: ["004"]
---

# TenantCreate Max Length Mismatch

## Problem Statement
`TenantCreate` schema defines `max_length=50` while the model and `RegisterRequest` use `max_length=56`. This inconsistency could cause confusion and unexpected validation failures.

## Findings
- Location: `src/app/schemas/tenant.py:10`
  - TenantCreate: `slug: str = Field(min_length=1, max_length=50)` ❌
- Location: `src/app/schemas/auth.py:41`
  - RegisterRequest: `tenant_slug: str = Field(min_length=1, max_length=56)` ✓
- Location: `src/app/models/public/tenant.py:13`
  - Model: `MAX_SLUG_LENGTH = 56` ✓
- Location: Migration `010_add_tenant_slug_length_constraint.py:36`
  - DB constraint: `length(slug) <= 56` ✓

## Proposed Solutions

### Option 1: Update TenantCreate to max_length=56
- **Pros**: Consistent with model, RegisterRequest, and DB constraint
- **Cons**: None
- **Effort**: Trivial
- **Risk**: Low

```python
slug: str = Field(min_length=1, max_length=56)
```

## Recommended Action
Update `TenantCreate` schema to use `max_length=56`.

## Technical Details
- **Affected Files**:
  - `src/app/schemas/tenant.py`
- **Related Components**: Tenant creation API
- **Database Changes**: No (DB already allows 56)

## Resources
- Original finding: REVIEW.md - IMPORTANT #1
- Related issues: Issue 004 (Slug validation mismatch)

## Acceptance Criteria
- [x] `TenantCreate.slug` uses `max_length=56`
- [x] Tests pass
- [x] Code reviewed

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P1 (Schema Consistency)
- Estimated effort: Trivial

**Learnings:**
- MAX_SLUG_LENGTH = 63 (PostgreSQL limit) - 7 ("tenant_" prefix) = 56
- This is a simple fix but important for API consistency

### 2025-12-16 - Resolution
**By:** Claude Code
**Actions:**
- Updated `TenantCreate.slug` from `max_length=50` to `max_length=56`
- Status changed from pending to done
- All acceptance criteria met

**Learnings:**
- Schema is now consistent with model, RegisterRequest, and DB constraint
- No breaking changes as this expands validation rather than restricts it

## Notes
Source: REVIEW.md analysis on 2025-12-16
