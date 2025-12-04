---
status: ready
priority: p1
issue_id: "020"
tags: [security, rate-limiting, auth, tokens]
dependencies: []
---

# Missing Rate Limiting on Refresh Endpoint

## Problem Statement
The `/api/v1/auth/refresh` endpoint has NO rate limiting applied. Login has 5/minute, register has 3/hour, but refresh tokens can be brute-forced without any restriction.

## Findings
- Location: `src/app/api/v1/auth.py:77`
- Login endpoint: `@limiter.limit("5/minute")` ✓
- Register endpoint: `@limiter.limit("3/hour")` ✓
- Refresh endpoint: NO RATE LIMIT ✗
- Logout endpoint: NO RATE LIMIT ✗

## Proposed Solutions

### Option 1: Add rate limiting to refresh and logout (Recommended)
```python
@limiter.limit("10/minute")
async def refresh(request: Request, refresh_data: RefreshRequest, service: AuthServiceDep) -> RefreshResponse:

@limiter.limit("5/minute")
async def logout(request: Request, refresh_data: RefreshRequest, service: AuthServiceDep) -> None:
```
- **Pros**: Prevents brute force attacks on token endpoints
- **Cons**: Legitimate users with many tabs may hit limits
- **Effort**: Small (< 15 minutes)
- **Risk**: Low

## Recommended Action
Implement Option 1 - add rate limiting to refresh (10/min) and logout (5/min).

## Technical Details
- **Affected Files**: `src/app/api/v1/auth.py`
- **Related Components**: slowapi rate limiter
- **Database Changes**: No

## Resources
- OWASP Rate Limiting: https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html

## Acceptance Criteria
- [ ] Refresh endpoint has rate limiting (10/minute)
- [ ] Logout endpoint has rate limiting (5/minute)
- [ ] Rate limit errors return 429 status code
- [ ] Tests pass

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P1 (Critical Security)
- Estimated effort: Small

**Learnings:**
- All auth endpoints should have rate limiting
- Refresh tokens are high-value attack targets

## Notes
Source: Triage session on 2025-12-04
