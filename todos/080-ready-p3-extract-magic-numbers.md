---
status: ready
priority: p3
issue_id: "080"
tags: [best-practices, maintainability, documentation, constants]
dependencies: []
---

# Hardcoded Magic Numbers

## Problem Statement
Magic numbers appear throughout the codebase without explanation. Values like `32` for token length, `20` for max concurrent activities lack documentation about why those specific values were chosen.

## Findings
- Location: Multiple locations throughout codebase
- Examples found:
  - `secrets.token_urlsafe(32)` - token length
  - `Field(min_length=8, max_length=100)` - password limits
  - `max_concurrent_activities=20` - worker config
  - Rate limit values
  - Timeout values
- No documentation of reasoning behind values
- Hard to maintain and review

## Proposed Solutions

### Option 1: Extract to named constants with documentation
- **Pros**: Self-documenting, easy to maintain, clear reasoning
- **Cons**: Minor refactor across files
- **Effort**: Small
- **Risk**: Low

```python
# src/app/core/constants.py

# Security tokens - 32 bytes = 256 bits of entropy
# Provides adequate security against brute force attacks
TOKEN_LENGTH_BYTES: Final[int] = 32

# Password requirements per NIST SP 800-63B guidelines
PASSWORD_MIN_LENGTH: Final[int] = 8
PASSWORD_MAX_LENGTH: Final[int] = 100

# Worker concurrency - tuned for 2 CPU cores
# Higher values may cause resource contention
WORKER_MAX_CONCURRENT_ACTIVITIES: Final[int] = 20
WORKER_MAX_CONCURRENT_WORKFLOWS: Final[int] = 100

# Timeouts
EMAIL_SEND_TIMEOUT_SECONDS: Final[int] = 10
DB_QUERY_TIMEOUT_SECONDS: Final[int] = 30

# Rate limits
AUTH_RATE_LIMIT_PER_MINUTE: Final[int] = 5
API_RATE_LIMIT_PER_MINUTE: Final[int] = 100
```

## Recommended Action
Create constants module with documented values and replace magic numbers throughout codebase.

## Technical Details
- **Affected Files**: New `src/app/core/constants.py`, multiple service/config files
- **Related Components**: Auth, Temporal workers, rate limiting
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Constants module created with documented values
- [ ] All magic numbers replaced with named constants
- [ ] Documentation explains reasoning for each value
- [ ] Tests updated to use constants
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Named constants improve code readability
- Documentation of "why" is as important as "what"

## Notes
Source: Triage session on 2025-12-18
