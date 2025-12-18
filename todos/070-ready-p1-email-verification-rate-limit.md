---
status: ready
priority: p1
issue_id: "070"
tags: [security, rate-limiting, auth, brute-force]
dependencies: []
---

# Email Verification Missing Per-Email Rate Limiting

## Problem Statement
The email verification endpoint has rate limiting at 5/minute, but this is per-IP only. An attacker could rotate IPs to bypass rate limiting and brute force verification tokens.

## Findings
- Location: `src/app/api/v1/auth.py:247`
- Current rate limit: `@limiter.limit("5/minute")` - per IP only
- No per-email tracking of failed attempts
- Token brute force feasible with IP rotation
- No exponential backoff on failures

## Proposed Solutions

### Option 1: Add per-email rate limiting with Redis
- **Pros**: Prevents brute force regardless of IP rotation
- **Cons**: Requires Redis, slightly more complex
- **Effort**: Medium
- **Risk**: Low

```python
async def check_email_rate_limit(email: str) -> bool:
    """Check and increment failed verification attempts for email."""
    redis = await get_redis()
    if not redis:
        return True  # Allow if Redis unavailable

    key = f"verify_attempts:{email}"
    attempts = await redis.incr(key)
    if attempts == 1:
        await redis.expire(key, 3600)  # 1 hour window

    return attempts <= 10  # Max 10 attempts per hour per email

async def reset_email_rate_limit(email: str) -> None:
    """Reset rate limit on successful verification."""
    redis = await get_redis()
    if redis:
        await redis.delete(f"verify_attempts:{email}")
```

### Option 2: Add exponential backoff
- **Pros**: Slows down attackers progressively
- **Cons**: May frustrate legitimate users
- **Effort**: Small
- **Risk**: Low

## Recommended Action
Implement per-email rate limiting with Redis, combined with exponential backoff delay.

## Technical Details
- **Affected Files**: `src/app/api/v1/auth.py`, `src/app/core/cache.py`
- **Related Components**: Email verification service, Redis cache
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Per-email rate limiting implemented
- [ ] Failed attempts tracked in Redis
- [ ] Exponential backoff on repeated failures
- [ ] Rate limit resets on successful verification
- [ ] Tests for rate limiting behavior
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- IP-based rate limiting alone is insufficient
- Multi-factor rate limiting (IP + resource identifier) provides better protection

## Notes
Source: Triage session on 2025-12-18
