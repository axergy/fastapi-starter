---
status: ready
priority: p2
issue_id: "021"
tags: [security, tokens, cryptography, timing-attack]
dependencies: []
---

# Token Hash Vulnerable to Timing Attacks

## Problem Statement
Refresh token validation uses plain SHA256 hash comparison without constant-time comparison. This makes the system vulnerable to timing attacks where attackers can deduce valid token hashes by measuring response times.

## Findings
- Location: `src/app/services/auth_service.py:124`
- Current implementation uses `sha256(refresh_token.encode()).hexdigest()`
- Database comparison likely uses standard string equality
- No HMAC used - plain hash is vulnerable to length extension attacks if modified

## Proposed Solutions

### Option 1: Use HMAC with constant-time comparison (Recommended)
```python
import hmac
import hashlib
from src.app.core.config import get_settings

def hash_refresh_token(token: str) -> str:
    """Hash refresh token using HMAC-SHA256."""
    settings = get_settings()
    return hmac.new(
        settings.jwt_secret_key.encode(),
        token.encode(),
        hashlib.sha256
    ).hexdigest()

def verify_token_hash(token: str, stored_hash: str) -> bool:
    """Verify token hash using constant-time comparison."""
    computed_hash = hash_refresh_token(token)
    return hmac.compare_digest(computed_hash, stored_hash)
```
- **Pros**: Prevents timing attacks, HMAC is more secure than plain hash
- **Cons**: Existing tokens in DB need migration or invalidation
- **Effort**: Small (< 1 hour)
- **Risk**: Medium (requires token migration strategy)

### Option 2: Keep SHA256 but add constant-time comparison
```python
import hmac
from hashlib import sha256

token_hash = sha256(refresh_token.encode()).hexdigest()
db_token = await self.token_repo.get_by_tenant(self.tenant_id)

# Constant-time comparison
if db_token and hmac.compare_digest(token_hash, db_token.token_hash):
    return create_access_token(...)
```
- **Pros**: Backward compatible with existing tokens
- **Cons**: Still uses plain SHA256 (less secure than HMAC)
- **Effort**: Small (< 30 minutes)
- **Risk**: Low

## Recommended Action
Implement Option 2 first (quick fix), then migrate to Option 1.

## Technical Details
- **Affected Files**:
  - `src/app/services/auth_service.py`
  - `src/app/core/security.py` (add helper functions)
- **Related Components**: Token repository, auth service
- **Database Changes**: No immediate changes (Option 2), token migration needed for Option 1

## Resources
- Python hmac.compare_digest: https://docs.python.org/3/library/hmac.html#hmac.compare_digest
- Timing Attacks: https://codahale.com/a-lesson-in-timing-attacks/

## Acceptance Criteria
- [ ] Token comparison uses `hmac.compare_digest()`
- [ ] No timing difference observable between valid/invalid tokens
- [ ] Existing refresh tokens continue to work
- [ ] Tests pass

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 (Important Security)
- Estimated effort: Small

**Learnings:**
- Always use constant-time comparison for secrets
- HMAC is preferred over plain hashing for tokens

## Notes
Source: Triage session on 2025-12-04
