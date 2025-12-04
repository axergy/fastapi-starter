---
status: ready
priority: p1
issue_id: "004"
tags: [security, jwt, secrets, configuration]
dependencies: []
---

# Weak JWT Secret in Example Configuration

## Problem Statement
The `.env.example` file contains a weak, predictable JWT secret placeholder. Developers commonly copy `.env.example` to `.env` without changing values, leading to production deployments with known/weak secrets.

## Findings
- Default JWT secret in `.env.example`: `change-this-to-a-secure-random-string`
- Location: `.env.example:5`
- No runtime validation that secret was changed
- No minimum length enforcement
- Attackers can forge valid JWTs if default secret is used

## Proposed Solutions

### Option 1: Add Pydantic validator for JWT secret (RECOMMENDED)
- **Pros**: Fails fast at startup, clear error message, enforces minimum security
- **Cons**: None
- **Effort**: Small (30 minutes)
- **Risk**: Low

Implementation:
```python
# In config.py
class Settings(BaseSettings):
    jwt_secret_key: str

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if v == "change-this-to-a-secure-random-string":
            raise ValueError(
                "JWT_SECRET_KEY must be changed from default value. "
                "Generate a secure secret with: openssl rand -hex 32"
            )
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v
```

## Recommended Action
Implement Option 1 - add Pydantic validator to reject default/weak secrets

## Technical Details
- **Affected Files**:
  - `src/app/core/config.py`
  - `.env.example` (update with better instructions)
- **Related Components**: Authentication, JWT token generation
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- OWASP Secrets Management: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html

## Acceptance Criteria
- [ ] Pydantic validator added for jwt_secret_key
- [ ] Rejects default placeholder value
- [ ] Enforces minimum 32 character length
- [ ] Clear error message with generation instructions
- [ ] .env.example updated with generation command comment
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P1 CRITICAL
- Estimated effort: Small (30 minutes)

**Learnings:**
- Default secrets in example files are a common attack vector
- Fail-fast validation prevents production misconfigurations

## Notes
Source: Triage session on 2025-12-04
