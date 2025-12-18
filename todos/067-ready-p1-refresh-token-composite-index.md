---
status: ready
priority: p1
issue_id: "067"
tags: [performance, database, index, auth]
dependencies: []
---

# Missing Index on RefreshToken Lookups

## Problem Statement
Token refresh operations query by `token_hash` and `tenant_id` frequently. Without a composite index on `(token_hash, tenant_id)`, this will require a full table scan or two separate index lookups on every token refresh (high frequency operation).

## Findings
- Location: `src/app/repositories/public/token.py:22-72`
- Query pattern: `SELECT * FROM refresh_tokens WHERE token_hash = ? AND tenant_id = ?`
- Token refresh happens every 15-60 minutes per active user
- No composite index exists for this query pattern
- Performance degrades as table grows

## Proposed Solutions

### Option 1: Add composite index migration
- **Pros**: Optimal query performance, simple implementation
- **Cons**: Requires migration
- **Effort**: Small
- **Risk**: Low

```python
def upgrade() -> None:
    op.create_index(
        'ix_refresh_tokens_hash_tenant',
        'refresh_tokens',
        ['token_hash', 'tenant_id'],
        schema='public'
    )

def downgrade() -> None:
    op.drop_index('ix_refresh_tokens_hash_tenant', table_name='refresh_tokens', schema='public')
```

## Recommended Action
Create new Alembic migration to add composite index on `(token_hash, tenant_id)`.

## Technical Details
- **Affected Files**: New migration file in `src/alembic/versions/`
- **Related Components**: Token repository, auth service
- **Database Changes**: Yes - adds index

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Migration created with composite index
- [ ] Index covers both token_hash and tenant_id columns
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
- High-frequency queries need proper indexing from the start
- Composite indexes are more efficient than multiple single-column indexes for AND conditions

## Notes
Source: Triage session on 2025-12-18
