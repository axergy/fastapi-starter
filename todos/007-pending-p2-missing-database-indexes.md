---
status: ready
priority: p2
issue_id: "007"
tags: [performance, database, indexes]
dependencies: []
---

# Missing Database Indexes for Performance

## Problem Statement
Missing composite indexes on frequently queried columns. Every authenticated request performs lookups on `user_tenant_membership` and `refresh_tokens` tables without proper indexes, causing full table scans that worsen as data grows.

## Findings
- Missing `(user_id, tenant_id)` index on `refresh_tokens`
- Missing `(user_id, tenant_id, is_active)` index on `user_tenant_membership`
- Missing `(tenant_id, is_active)` index on `user_tenant_membership`
- Location: `src/alembic/versions/001_initial.py`
- Every auth request does sequential scan
- Performance degrades O(n) instead of O(log n)

## Proposed Solutions

### Option 1: Add composite indexes via new migration (RECOMMENDED)
- **Pros**: Non-breaking, improves query performance significantly
- **Cons**: Migration required, brief lock during index creation
- **Effort**: Small (1 hour)
- **Risk**: Low

Implementation:
```python
# New migration file
def upgrade() -> None:
    # For refresh_tokens - improves token refresh queries
    op.create_index(
        "ix_refresh_tokens_user_tenant",
        "refresh_tokens",
        ["user_id", "tenant_id"],
        unique=False
    )

    # For membership lookups - critical for auth performance
    op.create_index(
        "ix_membership_user_tenant_active",
        "user_tenant_membership",
        ["user_id", "tenant_id", "is_active"],
        unique=False
    )

    # For listing tenant's users
    op.create_index(
        "ix_membership_tenant_active",
        "user_tenant_membership",
        ["tenant_id", "is_active"],
        unique=False
    )

def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_user_tenant")
    op.drop_index("ix_membership_user_tenant_active")
    op.drop_index("ix_membership_tenant_active")
```

## Recommended Action
Implement Option 1 - add indexes via migration

## Technical Details
- **Affected Files**:
  - New migration file in `src/alembic/versions/`
- **Related Components**: Authentication, token refresh, membership queries
- **Database Changes**: Yes - adds 3 composite indexes

## Resources
- Original finding: Code review triage session
- PostgreSQL indexing: https://www.postgresql.org/docs/current/indexes.html

## Acceptance Criteria
- [ ] New migration created with composite indexes
- [ ] Index on refresh_tokens(user_id, tenant_id)
- [ ] Index on user_tenant_membership(user_id, tenant_id, is_active)
- [ ] Index on user_tenant_membership(tenant_id, is_active)
- [ ] Downgrade removes indexes
- [ ] Migration tested locally
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 IMPORTANT
- Estimated effort: Small (1 hour)

**Learnings:**
- Composite indexes critical for multi-column WHERE clauses
- Index order matters - leftmost columns should be most selective

## Notes
Source: Triage session on 2025-12-04
