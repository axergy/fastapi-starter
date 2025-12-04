---
status: ready
priority: p2
issue_id: "025"
tags: [data-integrity, database, constraints, migration]
dependencies: []
---

# Missing Unique Constraint on User-Tenant Membership

## Problem Statement
The `user_tenant_membership` table lacks a UNIQUE constraint on the `(user_id, tenant_id)` composite key. This allows duplicate memberships to be created for the same user-tenant pair, violating business logic that assumes one membership per pair.

## Findings
- Location: `src/alembic/versions/001_initial.py` (user_tenant_membership table)
- No unique constraint on (user_id, tenant_id) composite key
- Business logic assumes one membership per user-tenant pair
- Race conditions could create duplicates

## Proposed Solutions

### Option 1: Add migration with unique constraint (Recommended)
Create new Alembic migration:
```python
"""Add unique constraint to user_tenant_membership

Revision ID: 005
Revises: 004
"""

from alembic import op

def upgrade() -> None:
    op.create_unique_constraint(
        "uq_user_tenant_membership_user_tenant",
        "user_tenant_membership",
        ["user_id", "tenant_id"]
    )

def downgrade() -> None:
    op.drop_constraint(
        "uq_user_tenant_membership_user_tenant",
        "user_tenant_membership",
        type_="unique"
    )
```

- **Pros**: Enforces data integrity at database level, prevents duplicates
- **Cons**: Migration will fail if duplicates already exist
- **Effort**: Small (< 30 minutes)
- **Risk**: Low (need to check for existing duplicates first)

## Recommended Action
Implement Option 1 - add migration with unique constraint after checking for duplicates.

## Technical Details
- **Affected Files**:
  - Create: `src/alembic/versions/005_add_membership_unique_constraint.py`
- **Related Components**: user_tenant_membership table, registration flow
- **Database Changes**: Yes - adds unique constraint

## Pre-Migration Check
Before running migration, verify no duplicates exist:
```sql
SELECT user_id, tenant_id, COUNT(*)
FROM user_tenant_membership
GROUP BY user_id, tenant_id
HAVING COUNT(*) > 1;
```

## Resources
- PostgreSQL Unique Constraints: https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-UNIQUE-CONSTRAINTS

## Acceptance Criteria
- [ ] Migration created with unique constraint
- [ ] No duplicate memberships exist before migration
- [ ] Migration runs successfully
- [ ] Duplicate insert attempts raise IntegrityError
- [ ] Tests pass

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 (Important - Data Integrity)
- Estimated effort: Small

**Learnings:**
- Unique constraints should be added early to prevent data issues
- Always check for existing violations before adding constraints

## Notes
Source: Triage session on 2025-12-04
