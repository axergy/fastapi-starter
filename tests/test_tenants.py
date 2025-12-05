import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from src.app.core import db
from src.app.main import create_app

pytestmark = pytest.mark.asyncio


async def test_health_check(engine: AsyncEngine) -> None:
    """Test health check endpoint returns detailed status."""
    # Use engine fixture to ensure proper DB setup, then dispose before app creates its own
    await db.dispose_engine()

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    # Accept both 200 (healthy) and 503 (degraded - Temporal might not be running)
    assert response.status_code in (200, 503)
    data = response.json()
    assert data["status"] in ("healthy", "degraded", "unhealthy")
    assert "database" in data
    assert "temporal" in data
    # Database should be healthy since we have the engine fixture
    assert data["database"] == "healthy"
