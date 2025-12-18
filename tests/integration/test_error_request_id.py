"""Tests for request_id in error responses."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from src.app.core.shutdown import request_tracker
from src.app.main import create_app
from src.app.temporal.client import reset_temporal_client

pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Generator[TestClient]:
    """Test client fixture with proper cleanup."""
    # Reset state before test
    request_tracker.reset()
    reset_temporal_client()

    app = create_app()
    with TestClient(app) as c:
        yield c

    # Reset state after test (lifespan sets shutting_down=True)
    request_tracker.reset()
    reset_temporal_client()


def test_http_exception_includes_request_id(client: TestClient) -> None:
    """Test that HTTPException responses include request_id."""
    # Make a request to a non-existent endpoint
    response = client.get("/api/v1/nonexistent-endpoint")

    # Should get 404
    assert response.status_code == 404

    # Should include request_id in response
    data = response.json()
    assert "request_id" in data, "request_id not found in error response"
    assert "detail" in data, "detail not found in error response"
    assert data["request_id"] is not None, "request_id is None"
    assert isinstance(data["request_id"], str), "request_id is not a string"


def test_bad_request_includes_request_id(client: TestClient) -> None:
    """Test that 400 responses include request_id."""
    # Try to access a protected endpoint without tenant header (gets 400)
    response = client.get("/api/v1/users/me")

    # Should get 400 (missing X-Tenant-Slug header)
    assert response.status_code == 400

    # Should include request_id in response
    data = response.json()
    assert "request_id" in data, "request_id not found in 400 response"
    assert "detail" in data, "detail not found in 400 response"


def test_request_id_format(client: TestClient) -> None:
    """Test that request_id follows expected format (UUID-like)."""
    response = client.get("/api/v1/nonexistent-endpoint")

    data = response.json()
    request_id = data["request_id"]

    # Should be a non-empty string
    assert request_id
    assert len(request_id) > 0

    # asgi-correlation-id typically generates UUID-like strings
    # Just verify it's a reasonable format (contains hyphens, right length)
    # UUID format: 8-4-4-4-12 = 36 characters
    if "-" in request_id:
        assert len(request_id) == 36, f"Unexpected request_id format: {request_id}"


def test_different_requests_have_different_ids(client: TestClient) -> None:
    """Test that different requests get different request IDs."""
    response1 = client.get("/api/v1/endpoint1")
    response2 = client.get("/api/v1/endpoint2")

    # Both should have request_id
    data1 = response1.json()
    data2 = response2.json()

    assert "request_id" in data1
    assert "request_id" in data2

    # IDs should be different
    assert data1["request_id"] != data2["request_id"], "Different requests have same request_id"
