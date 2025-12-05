"""Security headers middleware (Helmet-style)."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses (similar to Helmet.js)."""

    # CSP for Swagger UI: requires inline scripts and CDN assets
    DEFAULT_CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
        "img-src 'self' data: cdn.jsdelivr.net; "
        "frame-ancestors 'none'"
    )

    def __init__(
        self,
        app: ASGIApp,
        content_security_policy: str | None = None,
        x_content_type_options: str = "nosniff",
        x_frame_options: str = "DENY",
        x_xss_protection: str = "1; mode=block",
        strict_transport_security: str = "max-age=31536000; includeSubDomains",
        referrer_policy: str = "strict-origin-when-cross-origin",
        permissions_policy: str | None = None,
    ):
        super().__init__(app)
        self.headers: dict[str, str] = {}
        csp = content_security_policy if content_security_policy is not None else self.DEFAULT_CSP
        if csp:
            self.headers["Content-Security-Policy"] = csp
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

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for header, value in self.headers.items():
            response.headers[header] = value
        return response
