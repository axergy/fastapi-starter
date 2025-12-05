import secrets
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from asgi_correlation_id import CorrelationIdMiddleware, correlation_id
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import RequestResponseEndpoint

from src.app.api.v1.router import api_router
from src.app.core.config import get_settings
from src.app.core.db import dispose_engine, get_public_session
from src.app.core.logging import (
    bind_request_context,
    clear_request_context,
    get_logger,
    setup_logging,
)
from src.app.core.rate_limit import limiter
from src.app.core.redis import close_redis, get_redis
from src.app.core.security import SecurityHeadersMiddleware
from src.app.core.shutdown import request_tracker
from src.app.temporal.client import close_temporal_client, get_temporal_client

logger = get_logger(__name__)

# Health check caching
_health_cache: dict[str, Any] | None = None
_health_cache_time: float = 0
HEALTH_CACHE_TTL = 10  # seconds


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan - startup and shutdown."""
    settings = get_settings()
    setup_logging(settings.debug)
    logger.info(f"Starting {settings.app_name}")

    yield

    # Graceful shutdown with proper request draining
    grace_period = settings.shutdown_grace_period
    logger.info(
        f"Shutdown initiated, waiting for {request_tracker.in_flight_count} in-flight requests..."
    )

    # Start shutdown mode to prevent new requests from being tracked
    await request_tracker.start_shutdown()

    # Wait for all in-flight requests to complete
    drained = await request_tracker.wait_for_drain(timeout=grace_period)
    if not drained:
        logger.warning(
            f"Shutdown timeout after {grace_period}s - "
            f"{request_tracker.in_flight_count} requests may not have completed"
        )

    logger.info("Closing connections...")
    await close_redis()
    await close_temporal_client()
    await dispose_engine()
    logger.info("Shutdown complete")


OPENAPI_TAGS = [
    {"name": "auth", "description": "Authentication and token management"},
    {"name": "users", "description": "User profile operations"},
    {"name": "tenants", "description": "Tenant management and provisioning"},
    {"name": "invites", "description": "Tenant invitation management"},
    {"name": "admin", "description": "Superuser administration endpoints"},
]


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Multi-tenant SaaS API with Temporal workflows",
        version="0.1.0",
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )

    # Exception handlers to include request_id in error responses
    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "request_id": correlation_id.get(),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "request_id": correlation_id.get(),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = correlation_id.get()
        logger.exception(
            "Unhandled exception",
            request_id=request_id,
            path=request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
            },
        )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # Add correlation ID middleware first (outermost middleware)
    app.add_middleware(CorrelationIdMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Request-ID"],
        expose_headers=["X-Total-Count"],
    )

    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Add logging context middleware
    @app.middleware("http")
    async def logging_context_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Bind request_id to log context for all requests."""
        clear_request_context()
        bind_request_context(correlation_id.get())
        try:
            response = await call_next(request)
            return response
        finally:
            clear_request_context()

    # Add request tracking middleware for graceful shutdown
    @app.middleware("http")
    async def track_requests_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Track in-flight requests for graceful shutdown."""
        # Don't track health checks or metrics
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)

        async with request_tracker.track_request():
            return await call_next(request)

    app.include_router(api_router)

    # Prometheus metrics instrumentation
    instrumentator = Instrumentator().instrument(app)

    # Protect /metrics endpoint if API key is configured
    if settings.metrics_api_key:
        api_key_header = APIKeyHeader(name="X-Metrics-Key", auto_error=False)

        async def verify_metrics_key(api_key: str | None = Depends(api_key_header)) -> None:
            if (
                api_key is None
                or settings.metrics_api_key is None
                or not secrets.compare_digest(api_key, settings.metrics_api_key)
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or missing metrics API key",
                )

        instrumentator.expose(app, endpoint="/metrics", dependencies=[Depends(verify_metrics_key)])
    else:
        instrumentator.expose(app, endpoint="/metrics")

    @app.get("/health")
    async def health() -> JSONResponse:
        """Health check with dependency validation and caching."""
        global _health_cache, _health_cache_time

        now = time.time()

        # If shutting down, always return draining status
        if request_tracker.is_shutting_down:
            return JSONResponse(
                content={
                    "status": "draining",
                    "in_flight_requests": request_tracker.in_flight_count,
                    "message": "Server is shutting down",
                },
                status_code=503,
            )

        # Return cached result if still valid
        if _health_cache and (now - _health_cache_time) < HEALTH_CACHE_TTL:
            cached_response = _health_cache.copy()
            cached_response["cached"] = True
            cached_response["cache_age_seconds"] = round(now - _health_cache_time, 1)
            status_code = 200 if cached_response["status"] == "healthy" else 503
            return JSONResponse(content=cached_response, status_code=status_code)

        # Perform actual health checks
        health_status: dict[str, Any] = {
            "status": "healthy",
            "database": "unknown",
            "temporal": "unknown",
            "redis": "not_configured",
            "cached": False,
            "timestamp": now,
        }

        # Check database
        try:
            async with get_public_session() as session:
                await session.execute(text("SELECT 1"))
            health_status["database"] = "healthy"
        except Exception as e:
            health_status["database"] = f"unhealthy: {str(e)}"
            health_status["status"] = "unhealthy"

        # Check Temporal (optional - don't fail if unavailable)
        try:
            await get_temporal_client()
            health_status["temporal"] = "healthy"
        except Exception as e:
            health_status["temporal"] = f"unhealthy: {str(e)}"
            # Temporal being down is "degraded", not fully unhealthy
            if health_status["status"] == "healthy":
                health_status["status"] = "degraded"

        # Check Redis (optional - don't fail if unavailable)
        redis = await get_redis()
        if redis:
            try:
                result = redis.ping()
                if hasattr(result, "__await__"):
                    await result
                health_status["redis"] = "healthy"
            except Exception as e:
                health_status["redis"] = f"unhealthy: {str(e)}"
                # Redis being down is "degraded", not fully unhealthy
                if health_status["status"] == "healthy":
                    health_status["status"] = "degraded"

        # Cache the result
        _health_cache = health_status
        _health_cache_time = now

        status_code = 200 if health_status["status"] == "healthy" else 503
        return JSONResponse(content=health_status, status_code=status_code)

    return app


app = create_app()
