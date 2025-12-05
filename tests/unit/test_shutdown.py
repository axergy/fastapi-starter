"""Tests for graceful shutdown functionality."""

import asyncio
import contextlib

import pytest

from src.app.core.shutdown import RequestTracker

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class TestRequestTracker:
    """Test the RequestTracker class."""

    async def test_request_tracking(self):
        """Test that requests are tracked correctly."""
        tracker = RequestTracker()

        assert tracker.in_flight_count == 0
        assert not tracker.is_shutting_down

        # Simulate a request
        async with tracker.track_request():
            assert tracker.in_flight_count == 1

        assert tracker.in_flight_count == 0

    async def test_multiple_concurrent_requests(self):
        """Test tracking multiple concurrent requests."""
        tracker = RequestTracker()

        async def mock_request(delay: float):
            async with tracker.track_request():
                await asyncio.sleep(delay)

        # Start 3 concurrent requests
        tasks = [
            asyncio.create_task(mock_request(0.1)),
            asyncio.create_task(mock_request(0.1)),
            asyncio.create_task(mock_request(0.1)),
        ]

        # Give tasks time to start
        await asyncio.sleep(0.05)
        assert tracker.in_flight_count == 3

        # Wait for all to complete
        await asyncio.gather(*tasks)
        assert tracker.in_flight_count == 0

    async def test_shutdown_with_no_requests(self):
        """Test shutdown when there are no in-flight requests."""
        tracker = RequestTracker()

        await tracker.start_shutdown()
        assert tracker.is_shutting_down

        # Should drain immediately
        drained = await tracker.wait_for_drain(timeout=1.0)
        assert drained is True

    async def test_shutdown_with_in_flight_requests(self):
        """Test shutdown waits for in-flight requests to complete."""
        tracker = RequestTracker()

        async def long_request():
            async with tracker.track_request():
                await asyncio.sleep(0.2)

        # Start a request
        task = asyncio.create_task(long_request())
        await asyncio.sleep(0.05)  # Let request start

        assert tracker.in_flight_count == 1

        # Start shutdown
        await tracker.start_shutdown()
        assert tracker.is_shutting_down

        # Should wait for request to complete
        drained = await tracker.wait_for_drain(timeout=1.0)
        assert drained is True
        assert tracker.in_flight_count == 0

        await task

    async def test_shutdown_timeout(self):
        """Test shutdown timeout when requests don't complete in time."""
        tracker = RequestTracker()

        async def very_long_request():
            async with tracker.track_request():
                await asyncio.sleep(5.0)  # Longer than timeout

        # Start a request
        task = asyncio.create_task(very_long_request())
        await asyncio.sleep(0.05)  # Let request start

        # Start shutdown
        await tracker.start_shutdown()

        # Should timeout
        drained = await tracker.wait_for_drain(timeout=0.1)
        assert drained is False
        assert tracker.in_flight_count == 1

        # Cancel the long request to clean up
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def test_shutdown_with_multiple_requests(self):
        """Test shutdown with multiple in-flight requests."""
        tracker = RequestTracker()

        async def request_with_delay(delay: float):
            async with tracker.track_request():
                await asyncio.sleep(delay)

        # Start multiple requests with different durations
        tasks = [
            asyncio.create_task(request_with_delay(0.1)),
            asyncio.create_task(request_with_delay(0.2)),
            asyncio.create_task(request_with_delay(0.15)),
        ]

        await asyncio.sleep(0.05)  # Let requests start
        assert tracker.in_flight_count == 3

        # Start shutdown
        await tracker.start_shutdown()

        # Should wait for all requests to complete
        drained = await tracker.wait_for_drain(timeout=1.0)
        assert drained is True
        assert tracker.in_flight_count == 0

        await asyncio.gather(*tasks)
