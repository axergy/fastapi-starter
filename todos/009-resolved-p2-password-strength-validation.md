---
status: ready
priority: p2
issue_id: "009"
tags: [security, authentication, validation]
dependencies: []
---

# No Password Strength Validation

## Problem Statement
Password validation only checks `min_length=8`. This allows weak passwords like "12345678" or "aaaaaaaa" which are trivial to brute force.

## Findings
- Only minimum length validation on passwords
- Location: `src/app/schemas/auth.py:32`
- Weak passwords like "12345678" are accepted
- No complexity requirements (uppercase, lowercase, digits)
- No common password check

## Proposed Solutions

### Option 1: Add Pydantic field validator (RECOMMENDED)
- **Pros**: Simple, validates at schema level, clear error messages
- **Cons**: None
- **Effort**: Small (1 hour)
- **Risk**: Low

Implementation:
```python
from pydantic import field_validator
import re

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Ensure password has minimum complexity."""
        if not re.search(r'[a-z]', v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r'[A-Z]', v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r'\d', v):
            raise ValueError("Password must contain at least one digit")

        # Check against common passwords
        common_passwords = ['password', '12345678', 'qwerty123']
        if v.lower() in common_passwords:
            raise ValueError("Password is too common")

        return v
```

### Option 2: Use password-strength library
- **Pros**: More comprehensive checks, entropy calculation
- **Cons**: Additional dependency
- **Effort**: Small (1-2 hours)
- **Risk**: Low

## Recommended Action
Implement Option 1 - simple regex-based validation

## Technical Details
- **Affected Files**:
  - `src/app/schemas/auth.py`
- **Related Components**: Registration, password change (if exists)
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- OWASP Password Guidelines: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html

## Acceptance Criteria
- [ ] Password validator added to RegisterRequest schema
- [ ] Requires at least one lowercase letter
- [ ] Requires at least one uppercase letter
- [ ] Requires at least one digit
- [ ] Rejects common passwords
- [ ] Clear error messages for each requirement
- [ ] Tests for validation logic
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 IMPORTANT
- Estimated effort: Small (1 hour)

**Learnings:**
- Minimum length alone is insufficient for password security
- Balance security with usability in error messages

## Notes
Source: Triage session on 2025-12-04
