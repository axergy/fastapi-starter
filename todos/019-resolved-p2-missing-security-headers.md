---
status: ready
priority: p2
issue_id: "019"
tags: [security, headers, middleware, helmet]
dependencies: []
---

# Missing Security Headers (Helmet-style Middleware)

## Problem Statement
The application lacks essential HTTP security headers that protect against common web vulnerabilities like clickjacking, MIME sniffing, and XSS attacks. Need a generic Helmet-style middleware similar to fastapi-helmet but implemented directly in the codebase.

## Findings
- Location: `src/app/main.py` (no security headers middleware)
- Missing headers: X-Frame-Options, X-Content-Type-Options, Strict-Transport-Security, CSP, etc.
- Reference implementation: https://github.com/AkhileshThykkat/fastapi-helmet/tree/main

## Proposed Solutions

### Option 1: Implement Helmet-style middleware (Recommended)
Create a configurable security headers middleware similar to fastapi-helmet:

```python
# src/app/core/security_headers.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        content_security_policy: str | None = "default-src 'self'",
        x_content_type_options: str = "nosniff",
        x_frame_options: str = "DENY",
        x_xss_protection: str = "1; mode=block",
        strict_transport_security: str = "max-age=31536000; includeSubDomains",
        referrer_policy: str = "strict-origin-when-cross-origin",
        permissions_policy: str | None = None,
    ):
        super().__init__(app)
        self.headers = {}
        if content_security_policy:
            self.headers["Content-Security-Policy"] = content_security_policy
        if x_content_type_options:
            self.headers["X-Content-Type-Options"] = x_content_type_options
        if x_frame_options:
            self.headers["X-Frame-Options"] = x_frame_options
        if x_xss_protection:
            self.headers["X-XSS-Protection"] = x_xss_protection
        if strict_transport_security:
            self.headers["Strict-Transport-Security"] = strict_transport_security
        if referrer_policy:
            self.headers["Referrer-Policy"] = referrer_policy
        if permissions_policy:
            self.headers["Permissions-Policy"] = permissions_policy

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in self.headers.items():
            response.headers[header] = value
        return response
```

- **Pros**: Configurable, no external dependency, follows helmet pattern
- **Cons**: Must maintain ourselves
- **Effort**: Small (< 1 hour)
- **Risk**: Low

## Recommended Action
Implement Option 1 - create Helmet-style configurable middleware.

## Technical Details
- **Affected Files**:
  - Create: `src/app/core/security_headers.py`
  - Modify: `src/app/main.py` (add middleware)
- **Related Components**: Middleware stack
- **Database Changes**: No

## Resources
- Reference: https://github.com/AkhileshThykkat/fastapi-helmet/tree/main
- OWASP Secure Headers: https://owasp.org/www-project-secure-headers/

## Acceptance Criteria
- [ ] SecurityHeadersMiddleware created with configurable options
- [ ] All standard security headers applied by default
- [ ] Headers can be customized via constructor parameters
- [ ] Middleware added to FastAPI app
- [ ] Tests verify headers are present in responses

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 (Important Security)
- User requested Helmet-style implementation (copy functionality, not install library)
- Estimated effort: Small

**Learnings:**
- Security headers are a defense-in-depth measure
- Configurable middleware allows environment-specific settings

## Notes
Source: Triage session on 2025-12-04
Do NOT install fastapi-helmet - implement the functionality directly.
