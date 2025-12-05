"""Tests for health check caching functionality."""

import time
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.app.core.health import reset_health_cache
from src.app.main import create_app

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def clear_health_cache():
    """Reset health cache before each test."""
    reset_health_cache()
    yield
    reset_health_cache()


async def test_health_check_caching():
    """Test that health check results are cached for 10 seconds."""
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # First request should hit the database
        response1 = await client.get("/health")
        data1 = response1.json()

        assert response1.status_code in (200, 503)
        assert "cached" in data1
        assert data1["cached"] is False
        assert "timestamp" in data1

        # Second request within 10 seconds should return cached result
        response2 = await client.get("/health")
        data2 = response2.json()

        assert response2.status_code in (200, 503)
        assert data2["cached"] is True
        assert "cache_age_seconds" in data2
        assert data2["cache_age_seconds"] < 10


async def test_health_check_cache_expiry():
    """Test that health check cache expires after TTL."""
    app = create_app()

    # Use a callable class to control time values
    class MockTime:
        def __init__(self):
            self.current_time = 0.0

        def __call__(self):
            return self.current_time

    mock_time = MockTime()

    with patch("src.app.core.health.time.time", mock_time):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # First request at t=0
            mock_time.current_time = 0.0
            response1 = await client.get("/health")
            data1 = response1.json()
            assert data1["cached"] is False

            # Second request at t=1 (within TTL)
            mock_time.current_time = 1.0
            response2 = await client.get("/health")
            data2 = response2.json()
            assert data2["cached"] is True

            # Third request at t=15 (after TTL expired)
            mock_time.current_time = 15.0
            response3 = await client.get("/health")
            data3 = response3.json()
            # This should be a fresh check since cache expired
            assert data3["cached"] is False


async def test_health_check_no_db_session_when_cached():
    """Test that cached health checks don't create database sessions."""
    app = create_app()

    with patch("src.app.core.health.get_public_session") as mock_session:
        mock_session.return_value.__aenter__ = AsyncMock()
        mock_session.return_value.__aexit__ = AsyncMock()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # First request should call get_public_session
            await client.get("/health")
            assert mock_session.call_count == 1

            # Second request should use cache, no new session
            await client.get("/health")
            assert mock_session.call_count == 1, "Cache should prevent new DB session"


async def test_health_check_includes_status_fields():
    """Test that health check response includes all required fields."""
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")
        data = response.json()

        # Check all required fields are present
        assert "status" in data
        assert "database" in data
        assert "temporal" in data
        assert "redis" in data
        assert "cached" in data
        assert "timestamp" in data

        # Validate field types
        assert isinstance(data["status"], str)
        assert isinstance(data["cached"], bool)
        assert isinstance(data["timestamp"], int | float)


async def test_health_check_cache_includes_age():
    """Test that cached responses include cache age."""
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # First request - not cached
        response1 = await client.get("/health")
        data1 = response1.json()
        assert "cache_age_seconds" not in data1

        # Small delay
        time.sleep(0.1)

        # Second request - cached
        response2 = await client.get("/health")
        data2 = response2.json()
        assert "cache_age_seconds" in data2
        assert data2["cache_age_seconds"] >= 0.1
        assert data2["cache_age_seconds"] < 10
