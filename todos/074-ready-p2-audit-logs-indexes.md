---
status: ready
priority: p2
issue_id: "074"
tags: [performance, database, index, audit]
dependencies: []
---

# Missing Index on Audit Logs Query Patterns

## Problem Statement
Audit logs are queried by `tenant_id`, `user_id`, `created_at` but there are no composite indexes for common query patterns. Performance will degrade significantly as audit logs accumulate.

## Findings
- Location: `src/app/models/public/audit.py`
- Common queries: list by tenant, list by user, filter by action
- All queries order by `created_at DESC`
- No composite indexes for these patterns
- Audit logs grow continuously - unbounded table

## Proposed Solutions

### Option 1: Add composite indexes for common query patterns
- **Pros**: Covers all common access patterns, significant performance improvement
- **Cons**: Slightly slower inserts, more disk space
- **Effort**: Small
- **Risk**: Low

```python
def upgrade() -> None:
    # Most common: list logs for tenant
    op.create_index(
        'ix_audit_logs_tenant_created',
        'audit_logs',
        ['tenant_id', sa.text('created_at DESC')],
        schema='public'
    )

    # List logs for specific user in tenant
    op.create_index(
        'ix_audit_logs_user_tenant',
        'audit_logs',
        ['user_id', 'tenant_id', sa.text('created_at DESC')],
        schema='public'
    )

    # Filter by action type
    op.create_index(
        'ix_audit_logs_action_created',
        'audit_logs',
        ['action', sa.text('created_at DESC')],
        schema='public'
    )

def downgrade() -> None:
    op.drop_index('ix_audit_logs_tenant_created', schema='public')
    op.drop_index('ix_audit_logs_user_tenant', schema='public')
    op.drop_index('ix_audit_logs_action_created', schema='public')
```

## Recommended Action
Create migration with composite indexes covering common audit log query patterns.

## Technical Details
- **Affected Files**: New migration file in `src/alembic/versions/`
- **Related Components**: Audit repository, admin endpoints
- **Database Changes**: Yes - adds 3 indexes

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Migration created with composite indexes
- [ ] Indexes cover tenant, user, and action query patterns
- [ ] DESC ordering included for created_at
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
- Audit logs are append-only and grow indefinitely
- Index strategy must account for common query patterns upfront

## Notes
Source: Triage session on 2025-12-18
