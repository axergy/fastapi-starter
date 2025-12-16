"""Logging configuration using structlog."""

import logging
import sys
from uuid import UUID

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars


def setup_logging(debug: bool = False) -> None:
    """Configure structlog for structured logging.

    Args:
        debug: If True, use colored console output. If False, use JSON for production.
    """
    # Set up standard library logging
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Configure structlog processors
    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if debug:
        # Human-readable colored output for development
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]
    else:
        # JSON output for production
        processors = shared_processors + [structlog.processors.JSONRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set library log levels to reduce noise
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("temporalio").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger instance.

    Args:
        name: Optional logger name.

    Returns:
        A bound structlog logger.
    """
    return structlog.get_logger(name)


def bind_request_context(request_id: str | None) -> None:
    """Bind request-level context to all subsequent log calls.

    Args:
        request_id: The correlation ID for the current request.
    """
    if request_id:
        bind_contextvars(request_id=request_id)


def bind_user_context(user_id: UUID, tenant_id: UUID, email: str | None = None) -> None:
    """Bind user-level context to all subsequent log calls.

    Args:
        user_id: The authenticated user's ID.
        tenant_id: The tenant ID from the request context.
        email: Optional user email for additional context.
               Only logged if settings.log_user_emails is True (GDPR compliance).
    """
    from src.app.core.config import get_settings

    bind_contextvars(
        user_id=str(user_id),
        tenant_id=str(tenant_id),
    )
    # Only log email if explicitly enabled (GDPR compliance)
    settings = get_settings()
    if email and settings.log_user_emails:
        bind_contextvars(user_email=email)


def clear_request_context() -> None:
    """Clear all request-scoped context."""
    clear_contextvars()
