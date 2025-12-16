---
id: "013"
title: "Alembic Public Schema Enforcement"
status: pending
priority: p1
source: "REVIEW.md - CRITICAL #4"
category: correctness
---

# Alembic Public Schema Enforcement

## Problem

Alembic `env.py` doesn't explicitly SET search_path for public migrations. With non-standard PostgreSQL search_path defaults, public tables could be created in the wrong schema.

## Risk

- **Migration failures**: Tables created in unexpected schema
- **Data loss**: Version table in wrong schema causes migration re-runs
- **Multi-tenant corruption**: Public tables mixed with tenant schemas

## Verified Findings

| Location | Line | Issue |
|----------|------|-------|
| `src/alembic/env.py` | 65-85 | Tenant migrations DO set search_path ✓ |
| `src/alembic/env.py` | 86-92 | Public migrations (else clause) MISSING `SET search_path TO public` |
| `src/alembic/env.py` | - | Missing `version_table_schema="public"` in configure() |

### Current Code (Problem)

```python
else:
    # Public migrations - no search_path set!
    await connection.run_sync(do_run_migrations)
```

## Fix

1. Add `SET search_path TO public` before running public migrations
2. Add `version_table_schema="public"` to `context.configure()`

### Code Changes

**src/alembic/env.py:**
```python
else:
    # Public migrations - explicitly set search_path
    await connection.execute(text("SET search_path TO public"))
    await connection.run_sync(do_run_migrations)
```

And in `do_run_migrations()`:
```python
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    version_table_schema="public",  # Add this
    ...
)
```

## Files to Modify

- `src/alembic/env.py`

## Acceptance Criteria

- [ ] Public migrations execute `SET search_path TO public` before running
- [ ] `version_table_schema="public"` added to context.configure()
- [ ] Verify existing migrations still run correctly
- [ ] Add comment explaining why explicit search_path is needed
