---
status: ready
priority: p1
issue_id: "001"
tags: [security, authentication, race-condition]
dependencies: []
---

# Token Refresh Race Condition - Replay Attack Vulnerability

## Problem Statement
The `refresh_access_token` method has a critical time-of-check-time-of-use (TOCTOU) race condition. After verifying a refresh token is valid in the database, there's no atomic revocation before issuing a new access token. An attacker can exploit this window to reuse a refresh token multiple times in parallel requests.

## Findings
- Location: `src/app/services/auth_service.py:112-154`
- The token validation and access token generation are not atomic
- No token rotation implemented - same refresh token can be reused
- Parallel requests can all pass validation before any revocation occurs

**Attack Scenario:**
1. Attacker obtains valid refresh token
2. Sends 100 parallel refresh requests
3. All requests pass the `get_valid_by_hash_and_tenant` check simultaneously
4. All 100 requests return new valid access tokens
5. Attacker now has 100 active access tokens from single refresh token

## Proposed Solutions

### Option 1: Implement Token Rotation with Atomic Revocation
- Revoke old refresh token BEFORE issuing new access token
- Issue new refresh token with each refresh operation
- Return both new access and refresh tokens in response
- **Pros**: Industry standard, prevents replay attacks completely
- **Cons**: Requires API response schema change
- **Effort**: Medium (2-4 hours)
- **Risk**: Low

## Recommended Action
Implement token rotation pattern

## Technical Details
- **Affected Files**:
  - `src/app/services/auth_service.py`
  - `src/app/api/v1/auth.py`
  - `src/app/schemas/auth.py`
- **Related Components**: Authentication system, token management
- **Database Changes**: No schema changes needed

## Resources
- Original finding: Code review triage session
- OWASP Token Best Practices: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html

## Acceptance Criteria
- [ ] Refresh token is atomically revoked before new tokens issued
- [ ] Token rotation implemented - new refresh token returned with each refresh
- [ ] Parallel refresh requests with same token result in only one success
- [ ] Tests cover race condition scenario
- [ ] API documentation updated for new response format

## Work Log

### 2025-12-05 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage session
- Categorized as P1 CRITICAL (Security)
- Estimated effort: Medium (2-4 hours)

**Learnings:**
- TOCTOU vulnerabilities are common in token refresh flows
- Token rotation is the industry standard mitigation

## Notes
Source: Triage session on 2025-12-05
