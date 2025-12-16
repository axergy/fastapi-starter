---
status: done
priority: p0
issue_id: "002"
tags: [security, redis, performance]
dependencies: []
---

# Redis Blacklist Uses Fixed TTL Instead of Remaining Token Expiry

## Problem Statement
Redis blacklist uses `settings.refresh_token_expire_days * 86400` (fixed constant) instead of the remaining token expiry time. This causes memory bloat in Redis for tokens revoked shortly after creation.

## Findings
- Location: `src/app/services/auth_service.py:204,244,281`
- Fixed TTL calculation: `ttl = settings.refresh_token_expire_days * 86400`
- Tokens revoked near creation stay in Redis for full configured TTL (7 days default)
- Comment at cache.py:12 says "should match token expiry" but doesn't use actual `expires_at`
- Memory impact: Unnecessary Redis entries for tokens that would have expired naturally

## Proposed Solutions

### Option 1: Calculate remaining TTL from token expiry
- **Pros**: Optimal memory usage, correct behavior
- **Cons**: Requires accessing `db_token.expires_at` in all locations
- **Effort**: Small
- **Risk**: Low

```python
from src.app.models.base import utc_now
remaining_ttl = max(0, int((db_token.expires_at - utc_now()).total_seconds()))
await blacklist_token(token_hash, remaining_ttl)
```

## Recommended Action
Update all three locations to use remaining TTL calculated from `expires_at`.

## Technical Details
- **Affected Files**:
  - `src/app/services/auth_service.py`
- **Related Components**: Token blacklisting, Redis cache
- **Database Changes**: No

## Resources
- Original finding: REVIEW.md - CRITICAL #2
- Related issues: Issue 001 (Logout tenant scope)

## Acceptance Criteria
- [ ] `refresh_access_token()` uses remaining TTL from old token's `expires_at`
- [ ] `revoke_refresh_token()` uses remaining TTL from token's `expires_at`
- [ ] `revoke_all_tokens_for_user()` uses remaining TTL for each token
- [ ] Unit test verifying TTL calculation is correct
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P0 (Performance/Memory Critical)
- Estimated effort: Small

**Learnings:**
- The `db_token.expires_at` field is already available in most locations
- Need to handle case where token is already expired (TTL = 0)

### 2025-12-16 - Resolution Complete
**By:** Claude Code Resolution Specialist
**Actions:**
- Updated `refresh_access_token()` to calculate remaining TTL from `db_token.expires_at`
- Updated `revoke_refresh_token()` to calculate remaining TTL from `db_token.expires_at`
- Created new repository method `get_active_tokens_for_user()` to retrieve full token objects
- Created new cache function `blacklist_tokens_with_ttls()` for bulk blacklisting with individual TTLs
- Updated `revoke_all_tokens_for_user()` to use remaining TTL for each token
- All changes use `max(0, int((expires_at - utc_now()).total_seconds()))` for TTL calculation
- Added import for `utc_now` from `src.app.models.base`

**Changes Made:**
- `/Users/netf/Projects/Axergy/fastapi-starter/src/app/services/auth_service.py`: Updated all three token blacklisting locations
- `/Users/netf/Projects/Axergy/fastapi-starter/src/app/repositories/public/token.py`: Added `get_active_tokens_for_user()` method
- `/Users/netf/Projects/Axergy/fastapi-starter/src/app/core/cache.py`: Added `blacklist_tokens_with_ttls()` function

**Resolution Summary:**
All three locations now use actual remaining token expiry time instead of fixed TTL. This prevents memory bloat in Redis by ensuring tokens are only blacklisted for their actual remaining lifetime.

## Notes
Source: REVIEW.md analysis on 2025-12-16
