"""Health check endpoint with dependency validation and caching."""

import secrets
import time
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from src.app.core.config import get_settings
from src.app.core.db import get_public_session
from src.app.core.redis import get_redis
from src.app.core.shutdown import request_tracker
from src.app.temporal.client import get_temporal_client

# Health check caching
_health_cache: dict[str, Any] | None = None
_health_cache_time: float = 0
HEALTH_CACHE_TTL = 10  # seconds


def reset_health_cache() -> None:
    """Reset health cache (for testing)."""
    global _health_cache, _health_cache_time
    _health_cache = None
    _health_cache_time = 0


def setup_health_endpoint(app: FastAPI) -> None:
    """Configure the health check endpoint."""

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
            health_status["database"] = f"unhealthy: {e!s}"
            health_status["status"] = "unhealthy"

        # Check Temporal (optional - don't fail if unavailable)
        try:
            await get_temporal_client()
            health_status["temporal"] = "healthy"
        except Exception as e:
            health_status["temporal"] = f"unhealthy: {e!s}"
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
                health_status["redis"] = f"unhealthy: {e!s}"
                # Redis being down is "degraded", not fully unhealthy
                if health_status["status"] == "healthy":
                    health_status["status"] = "degraded"

        # Cache the result
        _health_cache = health_status
        _health_cache_time = now

        status_code = 200 if health_status["status"] == "healthy" else 503
        return JSONResponse(content=health_status, status_code=status_code)


def setup_metrics(app: FastAPI) -> None:
    """Configure Prometheus metrics with optional API key protection."""
    settings = get_settings()
    instrumentator = Instrumentator().instrument(app)

    if settings.metrics_api_key:
        api_key_header = APIKeyHeader(name="X-Metrics-Key", auto_error=False)

        async def verify_metrics_key(
            api_key: str | None = Depends(api_key_header),
        ) -> None:
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
