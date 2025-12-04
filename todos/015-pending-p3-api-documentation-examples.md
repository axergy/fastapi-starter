---
status: ready
priority: p3
issue_id: "015"
tags: [documentation, api, developer-experience]
dependencies: []
---

# Missing API Documentation Examples

## Problem Statement
API endpoints lack OpenAPI examples, making the auto-generated docs less useful for developers integrating with the API.

## Findings
- No example request/response bodies in OpenAPI docs
- Location: All API endpoints
- Swagger UI shows schemas but no concrete examples
- Developers must guess at correct formats

## Proposed Solutions

### Option 1: Add response examples to endpoint decorators (RECOMMENDED)
- **Pros**: Rich documentation, better DX, self-documenting API
- **Cons**: Some boilerplate
- **Effort**: Small (2-3 hours)
- **Risk**: Low

Implementation:
```python
@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        200: {
            "description": "Successful authentication",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIs...",
                        "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
                        "token_type": "bearer"
                    }
                }
            }
        },
        401: {
            "description": "Invalid credentials"
        }
    }
)
async def login(...):
    """Authenticate user and return tokens.

    Requires X-Tenant-ID header. User must have membership in the tenant.
    """
```

## Recommended Action
Implement Option 1 - add examples to all endpoints

## Technical Details
- **Affected Files**:
  - `src/app/api/v1/auth.py`
  - `src/app/api/v1/tenants.py`
  - `src/app/api/v1/users.py`
  - All other API endpoint files
- **Related Components**: OpenAPI/Swagger documentation
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- FastAPI responses: https://fastapi.tiangolo.com/advanced/additional-responses/

## Acceptance Criteria
- [ ] All endpoints have example responses
- [ ] Error responses documented with examples
- [ ] Request body examples where applicable
- [ ] Swagger UI shows meaningful examples
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P3 NICE-TO-HAVE
- Estimated effort: Small (2-3 hours)

**Learnings:**
- Good API documentation reduces integration friction
- Examples more useful than just schemas

## Notes
Source: Triage session on 2025-12-04
