"""Application middlewares."""

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app.core.config import Settings
from src.app.core.rate_limit import global_rate_limit_middleware

from .logging_context import logging_context_middleware
from .request_context import RequestContextMiddleware
from .request_tracking import request_tracking_middleware
from .security_headers import SecurityHeadersMiddleware

__all__ = [
    "setup_middlewares",
    "RequestContextMiddleware",
    "SecurityHeadersMiddleware",
    "logging_context_middleware",
    "request_tracking_middleware",
    "global_rate_limit_middleware",
]


def setup_middlewares(app: FastAPI, settings: Settings) -> None:
    """Configure all application middlewares.

    Middleware order matters - outermost middleware runs first.
    """
    # Correlation ID - generates/propagates X-Request-ID
    app.add_middleware(CorrelationIdMiddleware)

    # CORS - handle cross-origin requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-Slug", "X-Request-ID"],
        expose_headers=["X-Total-Count"],
    )

    # Security headers (Helmet-style)
    # Use stricter CSP in production when OpenAPI docs are disabled
    csp = None  # Use default (development CSP with unsafe-inline for Swagger)
    if not settings.enable_openapi and settings.csp_production:
        csp = settings.csp_production
    app.add_middleware(SecurityHeadersMiddleware, content_security_policy=csp)

    # Logging context - binds request_id to structlog context
    @app.middleware("http")
    async def _logging_context(request, call_next):  # type: ignore[no-untyped-def]
        return await logging_context_middleware(request, call_next)

    # Request context - unified context initialization (audit + assumed identity)
    app.add_middleware(RequestContextMiddleware)

    # Request tracking - for graceful shutdown
    @app.middleware("http")
    async def _request_tracking(request, call_next):  # type: ignore[no-untyped-def]
        return await request_tracking_middleware(request, call_next)

    # Global rate limiting - applies BEFORE tenant validation (DoS protection)
    # This is the innermost middleware, runs first on request
    @app.middleware("http")
    async def _global_rate_limit(request, call_next):  # type: ignore[no-untyped-def]
        return await global_rate_limit_middleware(request, call_next)
