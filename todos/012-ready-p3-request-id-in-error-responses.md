---
status: resolved
priority: p3
issue_id: "012"
tags: [observability, error-handling, developer-experience]
dependencies: []
---

# Missing Request ID in Error Responses

## Problem Statement
Error responses don't include the correlation ID (X-Request-ID) from `CorrelationIdMiddleware`, making it difficult to trace errors in logs. When users report errors, support has no way to correlate the error with server-side logs.

## Findings
- Location: Multiple API endpoints (no custom exception handler)
- `CorrelationIdMiddleware` generates request IDs
- Request ID appears in logs but not in error responses
- Users cannot report request IDs for debugging

**Problem Scenario:**
1. User encounters error (e.g., 500 Internal Server Error)
2. User reports error to support: "I got an error"
3. Support asks: "What was the request ID?"
4. User: "It wasn't in the response"
5. Support cannot trace the specific request in logs

**Current Error Response:**
```json
{
  "detail": "Internal server error"
}
```

**Desired Error Response:**
```json
{
  "detail": "Internal server error",
  "request_id": "abc123-def456-..."
}
```

## Proposed Solutions

### Option 1: Custom Exception Handlers
- Add exception handlers for HTTPException and generic exceptions
- Include request ID from correlation middleware in all error responses
- **Pros**: Simple, covers all error types
- **Cons**: Need to handle multiple exception types
- **Effort**: Small (1 hour)
- **Risk**: Low

**Implementation:**
```python
from asgi_correlation_id import correlation_id

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "request_id": correlation_id.get(),
        },
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": correlation_id.get(),
        },
    )
```

## Recommended Action
Implement custom exception handlers that include request ID

## Technical Details
- **Affected Files**:
  - `src/app/main.py` - Add exception handlers
- **Related Components**: Error handling, logging, support workflows
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- asgi-correlation-id docs: https://github.com/snok/asgi-correlation-id

## Acceptance Criteria
- [ ] HTTPException responses include request_id
- [ ] Unhandled exceptions return 500 with request_id
- [ ] Request ID matches X-Request-ID header
- [ ] Request ID matches log entries
- [ ] Tests verify request_id in error responses

## Work Log

### 2025-12-05 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage session
- Categorized as P3 NICE-TO-HAVE (Observability)
- Estimated effort: Small (1 hour)

**Learnings:**
- Request IDs enable log correlation for debugging
- Error responses should be actionable for users/support

## Notes
Source: Triage session on 2025-12-05
Quick win for improving support experience.
