import pytest
from httpx import ASGITransport, AsyncClient

from src.app.main import app

pytestmark = pytest.mark.asyncio


async def test_health_check() -> None:
    """Test health check endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
