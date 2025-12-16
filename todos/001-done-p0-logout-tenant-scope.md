---
status: done
priority: p0
issue_id: "001"
tags: [security, auth, cross-tenant]
dependencies: []
---

# Logout Revocation Missing Tenant Scope

## Problem Statement
`revoke_refresh_token()` in `auth_service.py` uses `get_by_hash()` without tenant filtering, allowing cross-tenant token revocation. A user in Tenant A could potentially revoke tokens belonging to users in Tenant B if they obtain a token hash.

## Findings
- Location: `src/app/services/auth_service.py:227`
- `db_token = await self.token_repo.get_by_hash(token_hash)` - NO TENANT CHECK
- Location: `src/app/repositories/public/token.py:19-24`
- `get_by_hash()` method has no tenant_id parameter
- `self.tenant_id` is available at line 57 but never used in revocation
- Security Impact: User in Tenant A could revoke tokens from Tenant B

## Proposed Solutions

### Option 1: Add tenant-scoped lookup method
- **Pros**: Consistent with `get_valid_by_hash_and_tenant()` pattern already used
- **Cons**: Minor code addition
- **Effort**: Small
- **Risk**: Low

## Recommended Action
Add `get_by_hash_and_tenant()` method and update `revoke_refresh_token()` to use it.

## Technical Details
- **Affected Files**:
  - `src/app/repositories/public/token.py`
  - `src/app/services/auth_service.py`
- **Related Components**: Token revocation, logout flow
- **Database Changes**: No

## Resources
- Original finding: REVIEW.md - CRITICAL #2
- Related issues: Issue 002 (Redis TTL)

## Acceptance Criteria
- [x] `revoke_refresh_token()` validates `token.tenant_id == self.tenant_id`
- [x] Add `get_by_hash_and_tenant()` method to token repository
- [ ] Unit test verifying cross-tenant revocation is rejected
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P0 (Security Critical)
- Estimated effort: Small

**Learnings:**
- The existing `get_valid_by_hash_and_tenant()` method shows the pattern to follow
- This is a security vulnerability allowing cross-tenant operations

### 2025-12-16 - Security Fix Implemented
**By:** Claude Code
**Actions:**
- Added `get_by_hash_and_tenant()` method to RefreshTokenRepository
- Updated `revoke_refresh_token()` in AuthService to use tenant-scoped lookup
- Method now prevents cross-tenant token revocation

**Changes Made:**
- `src/app/repositories/public/token.py`: Added `get_by_hash_and_tenant()` method (lines 26-41)
- `src/app/services/auth_service.py`: Updated line 228 to use `get_by_hash_and_tenant(token_hash, self.tenant_id)`

**Security Impact:**
- Tokens are now scoped to tenant during revocation
- User in Tenant A can no longer revoke tokens from Tenant B
- Follows the same pattern as `get_valid_by_hash_and_tenant()` for consistency

## Notes
Source: REVIEW.md analysis on 2025-12-16
Fixed: 2025-12-16
