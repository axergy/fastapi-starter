---
status: ready
priority: p2
issue_id: "012"
tags: [security, cryptography, authentication, configuration]
dependencies: []
---

# Hardcoded Argon2 Parameters May Be Insufficient

## Problem Statement
Argon2 parameters are hardcoded with `time_cost=2`, which is below OWASP recommendations. Parameters should be configurable and use stronger defaults.

## Findings
- Hardcoded Argon2 parameters
- Location: `src/app/core/security.py:10-14`
- `time_cost=2` is below OWASP recommendation of 3+
- Not configurable per environment
- Weaker hashes easier to brute force after breach

## Proposed Solutions

### Option 1: Make parameters configurable via settings (RECOMMENDED)
- **Pros**: Environment-specific tuning, follows best practices
- **Cons**: Slight code change
- **Effort**: Small (30 minutes)
- **Risk**: Low

Implementation:
```python
# In config.py
class Settings(BaseSettings):
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 1

# In security.py
def _create_password_hasher() -> argon2.PasswordHasher:
    settings = get_settings()
    return argon2.PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost,
        parallelism=settings.argon2_parallelism,
    )

_password_hasher = _create_password_hasher()
```

## Recommended Action
Implement Option 1 - configurable parameters with stronger defaults

## Technical Details
- **Affected Files**:
  - `src/app/core/security.py`
  - `src/app/core/config.py`
  - `.env.example`
- **Related Components**: Password hashing, authentication
- **Database Changes**: No (existing hashes remain valid)

## Resources
- Original finding: Code review triage session
- OWASP Password Storage: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- Argon2 recommendations: https://argon2-cffi.readthedocs.io/en/stable/parameters.html

## Acceptance Criteria
- [ ] Argon2 parameters moved to Settings
- [ ] Default time_cost increased to 3
- [ ] Parameters configurable via environment variables
- [ ] .env.example updated with defaults
- [ ] Existing password verification still works
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 IMPORTANT
- Estimated effort: Small (30 minutes)

**Learnings:**
- Password hashing parameters should be tunable per environment
- Higher time_cost = slower hashing = harder to brute force

## Notes
Source: Triage session on 2025-12-04
