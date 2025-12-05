---
status: ready
priority: p2
issue_id: "007"
tags: [security, rate-limiting, dos-prevention]
dependencies: []
---

# Missing Rate Limiting on Invite Acceptance

## Problem Statement
The public invite acceptance endpoint (`/invites/t/{token}/accept`) has no rate limiting, allowing attackers to brute force invite tokens or perform DoS attacks by repeatedly creating users. The endpoint is unauthenticated and token-based, making it a prime target for abuse.

## Findings
- Location: `src/app/api/v1/invites.py:310-464`
- Endpoint is public (no authentication required)
- Token-based access (vulnerable to enumeration)
- No rate limiting currently applied
- Can create users and send verification emails

**Problem Scenario:**
1. Attacker targets `/invites/t/{token}/accept` endpoint
2. No rate limiting allows unlimited requests
3. Attacker can:
   - Brute force invite tokens (enumeration attack)
   - Create thousands of fake user accounts
   - Exhaust email service quotas (verification emails)
   - Overload database with membership records

## Proposed Solutions

### Option 1: Add Rate Limiting Decorator
- Add `@limiter.limit("5/hour")` per IP address
- Simple, quick implementation using existing slowapi setup
- **Pros**: Fast to implement, uses existing infrastructure
- **Cons**: May be too restrictive for legitimate bulk invites
- **Effort**: Small (<1 hour)
- **Risk**: Low

**Proposed Implementation:**
```python
@router.post("/t/{token}/accept", ...)
@limiter.limit("5/hour")
async def accept_invite(request: Request, ...):
```

### Option 2: Token-Specific Rate Limiting
- Rate limit per token (e.g., 3 attempts per token per hour)
- Prevents repeated attempts on same invite
- **Pros**: More granular protection
- **Cons**: Slightly more complex
- **Effort**: Small (1-2 hours)
- **Risk**: Low

## Recommended Action
Implement Option 1 (IP-based rate limiting) as quick win, consider Option 2 for defense in depth

## Technical Details
- **Affected Files**:
  - `src/app/api/v1/invites.py`
- **Related Components**: Invite flow, user registration
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- OWASP Rate Limiting: https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html

## Acceptance Criteria
- [ ] Rate limiting applied to `/invites/t/{token}/accept` endpoint
- [ ] Returns 429 Too Many Requests when limit exceeded
- [ ] Rate limit logged for security monitoring
- [ ] Tests verify rate limiting behavior

## Work Log

### 2025-12-05 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage session
- Categorized as P2 IMPORTANT (Security - DoS)
- Estimated effort: Small (<1 hour)

**Learnings:**
- Public endpoints need rate limiting
- Token-based endpoints are prime targets for enumeration

## Notes
Source: Triage session on 2025-12-05
Quick win - can be implemented in minutes.
