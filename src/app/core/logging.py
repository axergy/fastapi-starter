import logging
import sys

from asgi_correlation_id import correlation_id


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get() or "-"
        return True


def setup_logging(debug: bool = False) -> None:
    """Configure application logging."""
    log_level = logging.DEBUG if debug else logging.INFO

    # Create handler with correlation ID filter
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(CorrelationIdFilter())

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(correlation_id)s] %(name)s - %(levelname)s - %(message)s',
        handlers=[handler]
    )

    # Set library log levels to reduce noise
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("temporalio").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
