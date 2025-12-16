---
id: "014"
title: "Slug Length DB Column Mismatch"
status: done
priority: p1
source: "REVIEW.md - CRITICAL #5"
category: correctness
---

# Slug Length DB Column Mismatch

## Problem

Database column is VARCHAR(50) but code validates up to 56 characters. Slugs between 50-56 characters pass validation but fail on DB insert with truncation or constraint violation.

## Risk

- **Data integrity**: Silent truncation of valid slugs
- **User confusion**: Validation passes but insert fails
- **Production bugs**: Edge case slugs cause 500 errors

## Verified Findings

| Location | Line | Issue |
|----------|------|-------|
| `src/alembic/versions/001_...` | 38 | `sa.Column("slug", ...length=50...)` - DB is 50 |
| `src/alembic/versions/010_...` | 36 | CHECK constraint for `length(slug) <= 56` |
| `src/app/models/public/tenant.py` | 13 | `MAX_SLUG_LENGTH = 56` |

### The Mismatch

```
Code validation:  max 56 chars ✓
CHECK constraint: max 56 chars ✓
Column width:     max 50 chars ✗ <-- MISMATCH
```

### Failure Scenario

```python
# This passes validation but fails insert
slug = "a" * 55  # 55 chars, valid per code
# INSERT fails: value too long for type character varying(50)
```

## Fix

Create migration to ALTER COLUMN slug to VARCHAR(56) to match code and CHECK constraint.

### Migration

```python
# src/alembic/versions/013_fix_slug_column_length.py
def upgrade() -> None:
    op.alter_column(
        "tenants",
        "slug",
        type_=sa.String(56),
        existing_type=sa.String(50),
        schema="public"
    )

def downgrade() -> None:
    # Note: This will fail if any slugs > 50 chars exist
    op.alter_column(
        "tenants",
        "slug",
        type_=sa.String(50),
        existing_type=sa.String(56),
        schema="public"
    )
```

## Files to Modify

- New: `src/alembic/versions/013_fix_slug_column_length.py`

## Acceptance Criteria

- [ ] Migration 013 created to ALTER COLUMN slug to VARCHAR(56)
- [ ] Migration includes downgrade (with warning about data loss)
- [ ] All slug-related constraints are consistent (56 chars)
- [ ] Integration test validates 56-char slugs work end-to-end
