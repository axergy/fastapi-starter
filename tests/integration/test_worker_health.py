"""Tests for Temporal worker health check endpoints."""

import asyncio
import contextlib
import socket

import pytest
from httpx import AsyncClient

from src.app.temporal.worker import run_health_server

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def get_free_port() -> int:
    """Get a free port number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


async def test_health_endpoint():
    """Test that health endpoint returns correct status."""
    port = get_free_port()

    # Start health server in background with new signature
    task = asyncio.create_task(run_health_server("all", ["test-queue"], port))

    # Give server time to start
    await asyncio.sleep(0.5)

    try:
        async with AsyncClient(base_url=f"http://localhost:{port}") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "temporal-worker"
            assert data["workload"] == "all"
            assert data["task_queues"] == ["test-queue"]
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def test_ready_endpoint():
    """Test that ready endpoint returns correct status."""
    port = get_free_port()

    # Start health server in background with new signature
    task = asyncio.create_task(run_health_server("all", ["test-queue"], port))

    # Give server time to start
    await asyncio.sleep(0.5)

    try:
        async with AsyncClient(base_url=f"http://localhost:{port}") as client:
            response = await client.get("/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
