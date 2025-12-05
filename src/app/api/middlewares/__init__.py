"""Application middlewares."""

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app.core.config import Settings

from .logging_context import logging_context_middleware
from .request_tracking import request_tracking_middleware
from .security_headers import SecurityHeadersMiddleware

__all__ = [
    "setup_middlewares",
    "SecurityHeadersMiddleware",
    "logging_context_middleware",
    "request_tracking_middleware",
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
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Request-ID"],
        expose_headers=["X-Total-Count"],
    )

    # Security headers (Helmet-style)
    app.add_middleware(SecurityHeadersMiddleware)

    # Logging context - binds request_id to structlog context
    @app.middleware("http")
    async def _logging_context(request, call_next):  # type: ignore[no-untyped-def]
        return await logging_context_middleware(request, call_next)

    # Request tracking - for graceful shutdown
    @app.middleware("http")
    async def _request_tracking(request, call_next):  # type: ignore[no-untyped-def]
        return await request_tracking_middleware(request, call_next)
