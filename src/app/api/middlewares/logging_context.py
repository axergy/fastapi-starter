"""Logging context middleware for request correlation."""

from asgi_correlation_id import correlation_id
from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from src.app.core.logging import bind_request_context, clear_request_context


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
