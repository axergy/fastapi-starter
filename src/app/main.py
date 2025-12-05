"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.app.api.middlewares import setup_middlewares
from src.app.api.v1.router import api_router
from src.app.core.config import get_settings
from src.app.core.db import dispose_engine
from src.app.core.exceptions import setup_exception_handlers
from src.app.core.health import setup_health_endpoint, setup_metrics
from src.app.core.logging import get_logger, setup_logging
from src.app.core.rate_limit import limiter
from src.app.core.redis import close_redis
from src.app.core.shutdown import request_tracker
from src.app.temporal.client import close_temporal_client

logger = get_logger(__name__)

OPENAPI_TAGS = [
    {"name": "auth", "description": "Authentication and token management"},
    {"name": "users", "description": "User profile operations"},
    {"name": "tenants", "description": "Tenant management and provisioning"},
    {"name": "invites", "description": "Tenant invitation management"},
    {"name": "admin", "description": "Superuser administration endpoints"},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan - startup and shutdown."""
    settings = get_settings()
    setup_logging(settings.debug)
    logger.info(f"Starting {settings.app_name}")

    yield

    # Graceful shutdown with request draining
    grace_period = settings.shutdown_grace_period
    logger.info(
        f"Shutdown initiated, waiting for {request_tracker.in_flight_count} in-flight requests..."
    )

    await request_tracker.start_shutdown()
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


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Multi-tenant SaaS API with Temporal workflows",
        version="0.1.0",
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # Setup components
    setup_exception_handlers(app)
    setup_middlewares(app, settings)
    app.include_router(api_router)
    setup_health_endpoint(app)
    setup_metrics(app)

    return app


app = create_app()
