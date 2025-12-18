---
status: ready
priority: p3
issue_id: "079"
tags: [error-handling, ux, api-design, consistency]
dependencies: []
---

# Inconsistent Error Messages

## Problem Statement
Error messages vary in format and detail level. Some include technical details, others are vague. No standardized error codes for programmatic handling.

## Findings
- Location: Multiple locations throughout codebase
- Inconsistent error message formats
- No error codes for programmatic handling
- Some errors leak implementation details
- Hard for frontend to build consistent error UI

Examples:
```python
raise ValueError("Email already registered")  # auth_service.py
raise ValueError(f"Tenant with slug '{tenant_slug}' already exists")  # registration_service.py
raise HTTPException(status_code=404, detail="Tenant not found")  # tenant.py
```

## Proposed Solutions

### Option 1: Implement error codes enum with standard format
- **Pros**: Consistent API, i18n support, programmatic handling
- **Cons**: Requires touching many files
- **Effort**: Medium
- **Risk**: Low

```python
from enum import Enum

class ErrorCode(str, Enum):
    EMAIL_EXISTS = "EMAIL_EXISTS"
    TENANT_SLUG_EXISTS = "TENANT_SLUG_EXISTS"
    TENANT_NOT_FOUND = "TENANT_NOT_FOUND"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    # ... etc

class ApplicationError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}

# Usage:
raise ApplicationError(
    ErrorCode.EMAIL_EXISTS,
    "This email is already registered"
)

# Response format:
{
    "error": {
        "code": "EMAIL_EXISTS",
        "message": "This email is already registered",
        "details": {}
    },
    "request_id": "..."
}
```

## Recommended Action
Create ApplicationError class with error codes enum and update exception handler to produce consistent responses.

## Technical Details
- **Affected Files**: `src/app/core/exceptions.py`, all service files, all endpoint files
- **Related Components**: Exception handlers, API responses
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] ErrorCode enum defined with all error types
- [ ] ApplicationError class implemented
- [ ] Exception handler produces consistent format
- [ ] Existing errors migrated to new format
- [ ] Frontend can rely on error codes
- [ ] Tests updated
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Consistent error handling improves developer experience
- Error codes enable i18n and programmatic error handling

## Notes
Source: Triage session on 2025-12-18
