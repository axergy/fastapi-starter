"""Request tracking middleware for graceful shutdown."""

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from src.app.core.shutdown import request_tracker


async def request_tracking_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    """Track in-flight requests for graceful shutdown."""
    # Don't track health checks or metrics
    if request.url.path in ["/health", "/metrics"]:
        return await call_next(request)

    async with request_tracker.track_request():
        return await call_next(request)
