import asyncio
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from src.app.api.v1.router import api_router
from src.app.core.config import get_settings
from src.app.core.db import dispose_engine, get_public_session
from src.app.core.logging import get_logger, setup_logging
from src.app.core.rate_limit import limiter
from src.app.core.security import SecurityHeadersMiddleware
from src.app.temporal.client import close_temporal_client, get_temporal_client

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan - startup and shutdown."""
    settings = get_settings()
    setup_logging(settings.debug)
    logger.info(f"Starting {settings.app_name}")

    yield

    # Graceful shutdown with drain period
    grace_period = settings.shutdown_grace_period
    logger.info(f"Shutdown initiated, draining requests for {grace_period}s...")

    # Allow in-flight requests to complete
    await asyncio.sleep(grace_period)

    logger.info("Closing connections...")
    await close_temporal_client()
    await dispose_engine()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
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
        """Health check with dependency validation."""
        health_status: dict[str, Any] = {
            "status": "healthy",
            "database": "unknown",
            "temporal": "unknown",
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

        status_code = 200 if health_status["status"] == "healthy" else 503
        return JSONResponse(content=health_status, status_code=status_code)

    return app


app = create_app()
