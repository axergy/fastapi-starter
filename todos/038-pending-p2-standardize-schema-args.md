---
status: done
priority: p2
issue_id: "038"
tags: [migrations, database, consistency]
dependencies: []
---

# Standardize Schema Arguments in Migrations

## Problem Statement
Inconsistent use of `schema="public"` argument in migration operations. Some migrations explicitly specify schema while others rely on `search_path` behavior. This creates inconsistency and makes the code harder to understand for contributors.

## Findings
- Location: Various migration files

- **Consistent (explicit schema):**
  - `src/alembic/versions/004_add_workflow_executions.py`: Uses `schema="public"` throughout

- **Inconsistent (missing schema):**
  - `src/alembic/versions/006_add_email_verification.py`: No schema argument
  - `src/alembic/versions/007_add_tenant_invites.py`: No schema argument
  - `src/alembic/versions/008_add_tenant_deleted_at.py`: No schema argument

- Example from migration 008:
  ```python
  op.create_index(
      "ix_tenants_deleted_at",
      "tenants",
      ["deleted_at"],
      # Missing schema="public"
      postgresql_where=sa.text("deleted_at IS NOT NULL"),
  )
  ```

- Also inconsistent `op.drop_index()` signatures using positional vs keyword arguments

## Proposed Solutions

### Option 1: Add explicit schema="public" to all public schema operations
- **Pros**: Explicit, clear, consistent with migration 004, self-documenting
- **Cons**: Slightly more verbose
- **Effort**: Small
- **Risk**: Low

### Recommended Pattern
```python
# Create operations
op.add_column("users", sa.Column(...), schema="public")
op.create_table("table_name", ..., schema="public")
op.create_index("idx_name", "table_name", [...], schema="public")

# Drop operations (use keyword arguments)
op.drop_index("ix_tenants_deleted_at", table_name="tenants", schema="public")
op.drop_constraint("constraint_name", "table_name", schema="public", type_="unique")
```

## Recommended Action
Update migrations 006, 007, 008 to use explicit `schema="public"` arguments for consistency with migration 004.

## Technical Details
- **Affected Files**:
  - `src/alembic/versions/006_add_email_verification.py`
  - `src/alembic/versions/007_add_tenant_invites.py`
  - `src/alembic/versions/008_add_tenant_deleted_at.py`
- **Related Components**: Alembic migrations
- **Database Changes**: No (just code style)

## Resources
- Original finding: REVIEW2.md - Medium #6
- Related issues: None

## Acceptance Criteria
- [ ] Migration 006 updated with schema="public" arguments
- [ ] Migration 007 updated with schema="public" arguments
- [ ] Migration 008 updated with schema="public" arguments
- [ ] Use keyword arguments for drop operations (not positional)
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2024-12-17 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW2.md code review
- Categorized as MEDIUM (consistency)
- Estimated effort: Small

**Learnings:**
- Explicit schema arguments are clearer than relying on search_path
- Consistency matters more than which style is chosen

## Notes
Source: REVIEW2.md Medium #6
Note: Migration 001 is the initial migration - changing it would be more disruptive. Focus on newer migrations (006+).
