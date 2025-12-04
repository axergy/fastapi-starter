import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from src.app.api.v1.router import api_router
from src.app.core.config import get_settings
from src.app.core.db import dispose_engine, get_public_session
from src.app.core.logging import setup_logging
from src.app.core.rate_limit import limiter
from src.app.temporal.client import close_temporal_client, get_temporal_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan - startup and shutdown."""
    settings = get_settings()
    setup_logging(settings.debug)
    logger.info(f"Starting {settings.app_name}")

    yield

    logger.info("Shutting down...")
    await close_temporal_client()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Add correlation ID middleware first (outermost middleware)
    app.add_middleware(CorrelationIdMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count"],
    )

    app.include_router(api_router)

    @app.get("/health")
    async def health() -> JSONResponse:
        """Health check with dependency validation."""
        health_status: dict[str, Any] = {
            "status": "healthy",
            "database": "unknown",
            "temporal": "unknown"
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
