"""Request tracking for graceful shutdown."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from src.app.core.logging import get_logger

logger = get_logger(__name__)


class RequestTracker:
    """Tracks in-flight requests for graceful shutdown."""

    def __init__(self) -> None:
        self._in_flight = 0
        self._shutting_down = False
        self._lock = asyncio.Lock()
        self._drain_event = asyncio.Event()

    @property
    def is_shutting_down(self) -> bool:
        """Check if the application is shutting down."""
        return self._shutting_down

    @property
    def in_flight_count(self) -> int:
        """Get the current number of in-flight requests."""
        return self._in_flight

    @asynccontextmanager
    async def track_request(self) -> AsyncGenerator[None]:
        """Context manager to track a request."""
        async with self._lock:
            self._in_flight += 1
            logger.debug(f"Request started, in-flight count: {self._in_flight}")
        try:
            yield
        finally:
            async with self._lock:
                self._in_flight -= 1
                logger.debug(f"Request completed, in-flight count: {self._in_flight}")
                if self._in_flight == 0 and self._shutting_down:
                    logger.info("All requests drained, setting drain event")
                    self._drain_event.set()

    async def start_shutdown(self) -> None:
        """Mark the application as shutting down."""
        logger.info("Request tracker entering shutdown mode")
        self._shutting_down = True
        async with self._lock:
            if self._in_flight == 0:
                logger.info("No in-flight requests, setting drain event immediately")
                self._drain_event.set()
            else:
                logger.info(f"Waiting for {self._in_flight} in-flight requests to complete")

    async def wait_for_drain(self, timeout: float) -> bool:
        """
        Wait for all in-flight requests to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if all requests completed within timeout, False otherwise
        """
        try:
            await asyncio.wait_for(self._drain_event.wait(), timeout=timeout)
            logger.info("All requests drained successfully")
            return True
        except TimeoutError:
            logger.warning(
                f"Shutdown timeout after {timeout}s - {self._in_flight} requests still in-flight"
            )
            return False

    def reset(self) -> None:
        """Reset tracker state. For testing only."""
        self._in_flight = 0
        self._shutting_down = False
        self._drain_event = asyncio.Event()


# Global request tracker instance
request_tracker = RequestTracker()
