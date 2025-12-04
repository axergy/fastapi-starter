"""Temporal Client - For starting workflows from API."""

from temporalio.client import Client

from src.app.core.config import get_settings

_client: Client | None = None


async def get_temporal_client() -> Client:
    """Get or create Temporal client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = await Client.connect(settings.temporal_host)
    return _client


async def close_temporal_client() -> None:
    """Close the Temporal client. Call during shutdown."""
    global _client
    if _client is not None:
        await _client.service_client.close()  # type: ignore[attr-defined]
        _client = None
