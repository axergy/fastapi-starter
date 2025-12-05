---
status: ready
priority: p2
issue_id: "005"
tags: [performance, database, indexing]
dependencies: []
---

# Missing Index on RefreshToken.expires_at

## Problem Statement
The `refresh_tokens` table queries frequently filter by `expires_at > utc_now()` but lacks an index on this column. As the table grows with expired tokens, query performance will degrade linearly, causing slow login/refresh operations.

## Findings
- Location: `src/app/models/public/auth.py:12-25`
- `get_valid_by_hash_and_tenant` query filters on:
  - `token_hash` (indexed ✓)
  - `tenant_id` (indexed ✓)
  - `revoked` (not indexed)
  - `expires_at` (NOT indexed ✗)
- No cleanup mechanism for expired tokens

**Problem Scenario:**
1. Table accumulates millions of expired refresh tokens over time
2. Every token refresh operation queries `expires_at > utc_now()`
3. Without index, PostgreSQL performs sequential scan on large table
4. Login/refresh operations become progressively slower
5. Database CPU spikes under load

**Current Model:**
```python
class RefreshToken(SQLModel, table=True):
    expires_at: datetime  # NO INDEX
```

## Proposed Solutions

### Option 1: Add Indexes + Cleanup Job
- Add single-column index on `expires_at`
- Add composite index `(tenant_id, expires_at)` for common query pattern
- Implement background job to purge expired tokens (e.g., daily)
- **Pros**: Complete solution, prevents table bloat
- **Cons**: Requires scheduled job setup
- **Effort**: Small (1-2 hours)
- **Risk**: Low

**Proposed Implementation:**
```python
class RefreshToken(SQLModel, table=True):
    __table_args__ = (
        Index('ix_refresh_tokens_expires_at', 'expires_at'),
        Index('ix_refresh_tokens_tenant_expires', 'tenant_id', 'expires_at'),
        {"schema": "public"}
    )
```

## Recommended Action
Add indexes via migration and implement token cleanup job

## Technical Details
- **Affected Files**:
  - `src/app/models/public/auth.py`
  - New migration file for indexes
  - New cleanup activity/job (optional but recommended)
- **Related Components**: Token validation, authentication
- **Database Changes**: Yes - ADD INDEX statements

## Resources
- Original finding: Code review triage session
- PostgreSQL indexing best practices

## Acceptance Criteria
- [ ] Index on `expires_at` column added via migration
- [ ] Composite index on `(tenant_id, expires_at)` added
- [ ] Query plan shows index usage for token validation queries
- [ ] (Optional) Background job purges tokens expired > 30 days
- [ ] Performance test shows improvement for large token tables

## Work Log

### 2025-12-05 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage session
- Categorized as P2 IMPORTANT (Performance)
- Estimated effort: Small (1-2 hours)

**Learnings:**
- Date/time columns used in range queries need indexes
- Token tables grow unbounded without cleanup jobs

## Notes
Source: Triage session on 2025-12-05
Consider combining with Issue #009 (Email Verification Token cleanup) for unified token management.
