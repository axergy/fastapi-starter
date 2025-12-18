---
status: ready
priority: p2
issue_id: "077"
tags: [data-integrity, database, constraint, membership]
dependencies: []
---

# Missing Constraint on UserTenantMembership

## Problem Statement
The membership table has composite primary key but no unique constraint preventing multiple active memberships. A user could have multiple rows for the same `(user_id, tenant_id)` pair if memberships are deactivated and reactivated.

## Findings
- Location: `src/app/models/public/user.py:30-41`
- Primary key: `(user_id, tenant_id)`
- `is_active` field controls membership state
- No constraint ensuring only one active membership per user-tenant pair
- Soft delete/reactivation could create duplicates

## Proposed Solutions

### Option 1: Add partial unique index on active memberships
- **Pros**: Enforces single active membership at DB level
- **Cons**: Requires migration
- **Effort**: Small
- **Risk**: Low

```python
def upgrade() -> None:
    op.execute("""
        CREATE UNIQUE INDEX ix_user_tenant_membership_active
        ON public.user_tenant_membership(user_id, tenant_id)
        WHERE is_active = true
    """)

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_user_tenant_membership_active")
```

### Option 2: Use upsert pattern in service layer
- **Pros**: No migration needed
- **Cons**: Doesn't prevent DB-level violations
- **Effort**: Small
- **Risk**: Medium (less safe)

## Recommended Action
Add partial unique index to enforce at database level - more reliable than application logic.

## Technical Details
- **Affected Files**: New migration file in `src/alembic/versions/`
- **Related Components**: Membership service, invite acceptance
- **Database Changes**: Yes - adds partial unique index

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Migration created with partial unique index
- [ ] Only one active membership allowed per user-tenant pair
- [ ] Existing data validated for duplicates before migration
- [ ] Migration tested (upgrade and downgrade)
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Partial unique indexes are powerful for enforcing business rules
- Database constraints are more reliable than application-level checks

## Notes
Source: Triage session on 2025-12-18
