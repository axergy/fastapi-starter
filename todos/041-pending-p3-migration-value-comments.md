---
status: done
priority: p3
issue_id: "041"
tags: [migrations, documentation, maintainability]
dependencies: []
---

# Add Comments to Migration Hardcoded Values

## Problem Statement
Migration files contain hardcoded values (string lengths, regex patterns) without comments explaining their origin. This makes it difficult for maintainers to understand where these values come from and whether they need to be updated if constants change.

## Findings
- Location: Various migration files

- `src/alembic/versions/010_add_tenant_slug_length_constraint.py` line 42:
  ```python
  # Hardcoded regex without comment explaining it matches TENANT_SLUG_REGEX
  sa.CheckConstraint(
      "slug ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'",
      name="ck_tenants_slug_format",
  )
  ```

- `src/alembic/versions/013_fix_slug_column_length.py` line 33:
  ```python
  # Hardcoded 56 without comment
  type_=sa.String(56),
  ```

- Developers may not realize these values come from `MAX_TENANT_SLUG_LENGTH` and `TENANT_SLUG_REGEX` constants

## Proposed Solutions

### Option 1: Add inline comments referencing source constants
- **Pros**: Clear, self-documenting, helps maintainers
- **Cons**: Comments can get stale
- **Effort**: Small
- **Risk**: Low

```python
# Migration 010:
sa.CheckConstraint(
    # Pattern from TENANT_SLUG_REGEX in src/app/core/security/validators.py
    "slug ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'",
    name="ck_tenants_slug_format",
)

# Migration 013:
type_=sa.String(56),  # MAX_TENANT_SLUG_LENGTH from src/app/core/security/validators.py
```

### Option 2: Import constants and use them directly
- **Pros**: No duplication, always in sync
- **Cons**: Breaks migration immutability principle (migrations should be frozen snapshots)
- **Effort**: Medium
- **Risk**: Medium (migrations shouldn't import app code)

## Recommended Action
Implement Option 1 - add comments. Migrations should remain frozen snapshots, so importing constants is not recommended. Comments provide documentation without breaking migration principles.

## Technical Details
- **Affected Files**:
  - `src/alembic/versions/010_add_tenant_slug_length_constraint.py`
  - `src/alembic/versions/013_fix_slug_column_length.py`
- **Related Components**: Alembic migrations, documentation
- **Database Changes**: No

## Resources
- Original finding: REVIEW2.md - Final note
- Related issues: None

## Acceptance Criteria
- [ ] Migration 010 has comment explaining regex source
- [ ] Migration 013 has comment explaining 56 value source
- [ ] Comments reference the source file path
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2024-12-17 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW2.md code review
- Categorized as POLISH (documentation)
- Estimated effort: Small

**Learnings:**
- Migrations should be treated as frozen snapshots
- Comments are the appropriate way to document hardcoded values in migrations
- Never import application constants into migrations

## Notes
Source: REVIEW2.md - Final note
Note: This is a documentation improvement only. The actual values should remain hardcoded in migrations to preserve migration immutability.
