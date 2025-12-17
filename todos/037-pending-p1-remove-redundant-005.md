---
status: done
priority: p1
issue_id: "037"
tags: [migrations, database, cleanup]
dependencies: []
---

# Remove Redundant Migration 005 Unique Constraint

## Problem Statement
Migration 005 creates a unique constraint on `(user_id, tenant_id)` which is already enforced by the composite primary key defined in migration 001. This is redundant and creates unnecessary overhead and confusion.

## Findings
- Location: `src/alembic/versions/001_initial.py:96`
  ```python
  sa.PrimaryKeyConstraint("user_id", "tenant_id"),
  ```

- Location: `src/alembic/versions/005_add_membership_unique_constraint.py:24-28`
  ```python
  op.create_unique_constraint(
      "uq_user_tenant_membership_user_tenant",
      "user_tenant_membership",
      ["user_id", "tenant_id"],
  )
  ```

- PostgreSQL primary keys already enforce uniqueness
- This creates a redundant index and constraint
- Violates DRY principle and confuses maintainers

## Proposed Solutions

### Option 1: Make migration 005 idempotent/no-op
- **Pros**: Backward-compatible with older DBs, safe for existing deployments
- **Cons**: Keeps a no-op migration file
- **Effort**: Small
- **Risk**: Low

```python
def _constraint_exists(constraint_name: str) -> bool:
    bind = op.get_bind()
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_namespace n ON n.oid = c.connamespace
                    WHERE n.nspname = 'public'
                      AND c.conname = :name
                )
                """
            ),
            {"name": constraint_name},
        ).scalar()
    )

def upgrade() -> None:
    if is_tenant_migration():
        return

    # If the table already has a composite PK, uniqueness is already guaranteed.
    if _constraint_exists("user_tenant_membership_pkey"):
        return

    # If the unique constraint already exists, do nothing (idempotent).
    if _constraint_exists("uq_user_tenant_membership_user_tenant"):
        return

    op.create_unique_constraint(
        "uq_user_tenant_membership_user_tenant",
        "user_tenant_membership",
        ["user_id", "tenant_id"],
        schema="public",
    )
```

### Option 2: Delete migration 005 entirely
- **Pros**: Cleaner, no dead code
- **Cons**: Breaks existing DBs that ran migration 005
- **Effort**: Small
- **Risk**: Medium (only for fresh installs)

## Recommended Action
Implement Option 1 - make migration 005 idempotent with proper guards. This is safer for a starter template that may have existing users.

## Technical Details
- **Affected Files**: `src/alembic/versions/005_add_membership_unique_constraint.py`
- **Related Components**: user_tenant_membership table, Alembic migrations
- **Database Changes**: No new changes (migration becomes no-op)

## Resources
- Original finding: REVIEW2.md - High #5
- Related issues: None

## Acceptance Criteria
- [ ] Migration 005 updated with constraint existence checks
- [ ] Migration is idempotent (safe to run multiple times)
- [ ] Skips if PK already provides uniqueness
- [ ] downgrade() also made idempotent
- [ ] schema="public" added to operations
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2024-12-17 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW2.md code review
- Categorized as HIGH (clarity)
- Estimated effort: Small

**Learnings:**
- Primary keys automatically enforce uniqueness
- Always check if constraint already exists before creating

## Notes
Source: REVIEW2.md High #5
