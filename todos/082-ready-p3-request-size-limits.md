---
status: ready
priority: p3
issue_id: "082"
tags: [security, dos, middleware, validation]
dependencies: []
---

# Missing Request Size Limits

## Problem Statement
No explicit request size limits. Large payloads (e.g., base64-encoded images, massive JSON bodies) could consume memory and cause denial of service.

## Findings
- Location: Application-wide
- No content-length validation
- Large payloads parsed entirely into memory
- No per-endpoint size limits
- Potential for memory exhaustion attacks

## Proposed Solutions

### Option 1: Add request size limit middleware
- **Pros**: Simple, catches all endpoints, configurable
- **Cons**: Blanket limit may not suit all endpoints
- **Effort**: Small
- **Risk**: Low

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB default

    async def dispatch(self, request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            if int(content_length) > self.MAX_REQUEST_SIZE:
                return JSONResponse(
                    {"detail": "Request body too large"},
                    status_code=413
                )
        return await call_next(request)

# In main.py
app.add_middleware(RequestSizeLimitMiddleware)
```

### Option 2: Use Starlette's built-in limit
- **Pros**: Even simpler
- **Cons**: Less control
- **Effort**: Small
- **Risk**: Low

```python
from starlette.middleware.trustedhost import TrustedHostMiddleware
# Configure in uvicorn: --limit-max-request-size
```

## Recommended Action
Add middleware with configurable size limit, defaulting to 10MB.

## Technical Details
- **Affected Files**: `src/app/api/middlewares/__init__.py`, `src/app/core/config.py`
- **Related Components**: All API endpoints
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Request size limit middleware implemented
- [ ] Limit configurable via settings
- [ ] Returns 413 for oversized requests
- [ ] Tests for size limit enforcement
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Always validate input size at the edge
- Memory exhaustion is a common DoS vector

## Notes
Source: Triage session on 2025-12-18
