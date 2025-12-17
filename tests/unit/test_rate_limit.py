"""Tests for rate limiting functionality (src/app/core/rate_limit.py).

Tests cover:
- get_rate_limit_key: Key generation from IP and tenant
- _check_in_memory_rate_limit: Token bucket algorithm
- global_rate_limit_middleware: Request flow and exemptions
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from src.app.core import rate_limit
from src.app.core.rate_limit import (
    _check_in_memory_rate_limit,
    get_rate_limit_key,
    global_rate_limit_middleware,
)

pytestmark = pytest.mark.unit


# --- Fixtures ---


@pytest.fixture(autouse=True)
def _reset_rate_limit_state(reset_rate_limit_buckets):
    """Reset rate limit module state before each test.

    Delegates to shared fixture in tests/conftest.py.
    """
    # Delegate to shared fixture in tests/conftest.py
    yield


@pytest.fixture
def mock_request() -> MagicMock:
    """Create a mock Starlette request."""
    request = MagicMock(spec=Request)
    request.headers = {}
    request.client = MagicMock()
    request.client.host = "192.168.1.100"
    request.url.path = "/api/v1/test"
    return request


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings with rate limit configuration.

    Sets app_env to 'development' to ensure rate limiting is active
    (rate limiting is disabled when app_env='testing').
    """
    settings = MagicMock()
    settings.app_env = "development"  # Enable rate limiting for tests
    settings.global_rate_limit_per_second = 10
    settings.global_rate_limit_burst = 20
    settings.redis_url = None
    return settings


# --- get_rate_limit_key Tests ---


class TestGetRateLimitKey:
    """Tests for get_rate_limit_key function."""

    def test_returns_ip_when_no_tenant_header(self, mock_request: MagicMock) -> None:
        """When X-Tenant-ID header is absent, returns just the IP."""
        mock_request.headers = {}

        with patch("src.app.core.rate_limit.get_remote_address", return_value="192.168.1.100"):
            key = get_rate_limit_key(mock_request)

        assert key == "192.168.1.100"

    def test_returns_ip_only_when_tenant_header_present(self, mock_request: MagicMock) -> None:
        """When X-Tenant-ID header is present, returns IP only (header ignored for security)."""
        mock_request.headers = {"X-Tenant-ID": "acme-corp"}

        with patch("src.app.core.rate_limit.get_remote_address", return_value="192.168.1.100"):
            key = get_rate_limit_key(mock_request)

        assert key == "192.168.1.100"

    def test_returns_unknown_when_ip_not_available(self, mock_request: MagicMock) -> None:
        """When IP cannot be determined, uses 'unknown' as fallback."""
        mock_request.headers = {}

        with patch("src.app.core.rate_limit.get_remote_address", return_value=None):
            key = get_rate_limit_key(mock_request)

        assert key == "unknown"

    def test_returns_unknown_when_ip_not_available_with_tenant(
        self, mock_request: MagicMock
    ) -> None:
        """When IP unavailable and tenant present, still returns 'unknown' (tenant ignored)."""
        mock_request.headers = {"X-Tenant-ID": "acme-corp"}

        with patch("src.app.core.rate_limit.get_remote_address", return_value=None):
            key = get_rate_limit_key(mock_request)

        assert key == "unknown"

    def test_empty_tenant_header_returns_ip_only(self, mock_request: MagicMock) -> None:
        """When X-Tenant-ID is empty string, returns just IP."""
        mock_request.headers = {"X-Tenant-ID": ""}

        with patch("src.app.core.rate_limit.get_remote_address", return_value="10.0.0.1"):
            key = get_rate_limit_key(mock_request)

        assert key == "10.0.0.1"


# --- _check_in_memory_rate_limit Tests ---


class TestCheckInMemoryRateLimit:
    """Tests for in-memory token bucket rate limiter."""

    async def test_allows_request_when_bucket_has_tokens(self, mock_settings: MagicMock) -> None:
        """Request is allowed when tokens are available."""
        with patch("src.app.core.rate_limit.get_settings", return_value=mock_settings):
            result = await _check_in_memory_rate_limit("192.168.1.1")

        assert result is True

    async def test_creates_new_bucket_for_new_client(self, mock_settings: MagicMock) -> None:
        """New client gets a fresh bucket with burst tokens."""
        with patch("src.app.core.rate_limit.get_settings", return_value=mock_settings):
            await _check_in_memory_rate_limit("new-client-ip")

        bucket = rate_limit._rate_limit_buckets["new-client-ip"]
        # Should have burst - 1 tokens after first request
        assert bucket["tokens"] == mock_settings.global_rate_limit_burst - 1

    async def test_decrements_tokens_on_each_request(self, mock_settings: MagicMock) -> None:
        """Each allowed request decrements the token count."""
        with patch("src.app.core.rate_limit.get_settings", return_value=mock_settings):
            await _check_in_memory_rate_limit("test-client")
            await _check_in_memory_rate_limit("test-client")
            await _check_in_memory_rate_limit("test-client")

        bucket = rate_limit._rate_limit_buckets["test-client"]
        # Started with burst=20, consumed 3
        assert bucket["tokens"] == pytest.approx(17, abs=0.1)

    async def test_denies_request_when_bucket_empty(self, mock_settings: MagicMock) -> None:
        """Request is denied when no tokens remain."""
        mock_settings.global_rate_limit_burst = 2

        with patch("src.app.core.rate_limit.get_settings", return_value=mock_settings):
            # Exhaust tokens
            assert await _check_in_memory_rate_limit("exhaust-client") is True
            assert await _check_in_memory_rate_limit("exhaust-client") is True
            # Third request should be denied
            assert await _check_in_memory_rate_limit("exhaust-client") is False

    async def test_replenishes_tokens_over_time(self, mock_settings: MagicMock) -> None:
        """Tokens are replenished based on elapsed time."""
        mock_settings.global_rate_limit_burst = 2
        mock_settings.global_rate_limit_per_second = 10

        with patch("src.app.core.rate_limit.get_settings", return_value=mock_settings):
            # Exhaust tokens
            await _check_in_memory_rate_limit("replenish-client")
            await _check_in_memory_rate_limit("replenish-client")
            assert await _check_in_memory_rate_limit("replenish-client") is False

            # Manipulate time to simulate 0.5 seconds passing
            bucket = rate_limit._rate_limit_buckets["replenish-client"]
            bucket["last_update"] = time.time() - 0.5  # 0.5s ago

            # Should have ~5 tokens replenished (10/s * 0.5s)
            # but capped at burst=2, so 2 tokens available
            assert await _check_in_memory_rate_limit("replenish-client") is True

    async def test_tokens_capped_at_burst_limit(self, mock_settings: MagicMock) -> None:
        """Token count never exceeds burst limit even with long idle time."""
        mock_settings.global_rate_limit_burst = 5
        mock_settings.global_rate_limit_per_second = 100

        with patch("src.app.core.rate_limit.get_settings", return_value=mock_settings):
            # Make one request
            await _check_in_memory_rate_limit("cap-client")

            # Simulate long idle time
            bucket = rate_limit._rate_limit_buckets["cap-client"]
            bucket["last_update"] = time.time() - 1000  # Long time ago

            # Make another request - should have max burst tokens
            await _check_in_memory_rate_limit("cap-client")

            # Tokens should be capped at burst - 1 (after request)
            assert bucket["tokens"] <= mock_settings.global_rate_limit_burst

    async def test_separate_buckets_per_client(self, mock_settings: MagicMock) -> None:
        """Each client IP has its own independent bucket."""
        mock_settings.global_rate_limit_burst = 2

        with patch("src.app.core.rate_limit.get_settings", return_value=mock_settings):
            # Exhaust client1
            await _check_in_memory_rate_limit("client1")
            await _check_in_memory_rate_limit("client1")
            assert await _check_in_memory_rate_limit("client1") is False

            # client2 should still have full bucket
            assert await _check_in_memory_rate_limit("client2") is True
            assert await _check_in_memory_rate_limit("client2") is True


# --- global_rate_limit_middleware Tests ---


class TestGlobalRateLimitMiddleware:
    """Tests for the global rate limit middleware."""

    async def test_exempt_paths_bypass_rate_limit(self, mock_request: MagicMock) -> None:
        """Monitoring endpoints are not rate limited."""
        call_next = AsyncMock(return_value=Response(content=b"OK"))

        exempt_paths = ["/health", "/metrics", "/docs", "/openapi.json", "/redoc"]

        for path in exempt_paths:
            mock_request.url.path = path
            response = await global_rate_limit_middleware(mock_request, call_next)
            assert response.body == b"OK", f"Path {path} should be exempt"

    async def test_allows_request_within_limit(
        self, mock_request: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Request within rate limit is forwarded to next handler."""
        call_next = AsyncMock(return_value=Response(content=b"Success"))
        mock_request.url.path = "/api/v1/users"

        with (
            patch("src.app.core.rate_limit.get_settings", return_value=mock_settings),
            patch("src.app.core.rate_limit.get_remote_address", return_value="10.0.0.1"),
            patch("src.app.core.rate_limit.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_get_redis.return_value = None  # No Redis, use in-memory

            response = await global_rate_limit_middleware(mock_request, call_next)

        assert response.body == b"Success"
        call_next.assert_called_once_with(mock_request)

    async def test_returns_429_when_rate_limited(
        self, mock_request: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Request exceeding rate limit returns 429 response."""
        mock_settings.global_rate_limit_burst = 1
        call_next = AsyncMock(return_value=Response(content=b"Success"))
        mock_request.url.path = "/api/v1/users"

        with (
            patch("src.app.core.rate_limit.get_settings", return_value=mock_settings),
            patch("src.app.core.rate_limit.get_remote_address", return_value="rate-limited"),
            patch("src.app.core.rate_limit.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_get_redis.return_value = None  # No Redis, use in-memory

            # First request allowed
            await global_rate_limit_middleware(mock_request, call_next)

            # Second request should be rate limited
            response = await global_rate_limit_middleware(mock_request, call_next)

        assert response.status_code == 429
        assert response.headers["Retry-After"] == "1"

    async def test_429_response_has_correct_body(
        self, mock_request: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Rate limited response contains proper error message."""
        mock_settings.global_rate_limit_burst = 0  # Immediately rate limited
        call_next = AsyncMock()
        mock_request.url.path = "/api/v1/test"

        with (
            patch("src.app.core.rate_limit.get_settings", return_value=mock_settings),
            patch("src.app.core.rate_limit.get_remote_address", return_value="test-ip"),
            patch("src.app.core.rate_limit.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_get_redis.return_value = None

            response = await global_rate_limit_middleware(mock_request, call_next)

        assert response.status_code == 429
        # JSONResponse body is bytes
        import json

        body = json.loads(response.body)
        assert body["detail"] == "Too many requests. Please slow down."
        assert body["retry_after"] == 1

    async def test_uses_unknown_when_ip_not_detected(
        self, mock_request: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Falls back to 'unknown' key when IP cannot be determined."""
        call_next = AsyncMock(return_value=Response(content=b"OK"))
        mock_request.url.path = "/api/v1/test"

        with (
            patch("src.app.core.rate_limit.get_settings", return_value=mock_settings),
            patch("src.app.core.rate_limit.get_remote_address", return_value=None),
            patch("src.app.core.rate_limit.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_get_redis.return_value = None

            await global_rate_limit_middleware(mock_request, call_next)

        # Should have created a bucket for "unknown"
        assert "unknown" in rate_limit._rate_limit_buckets


# --- _check_global_rate_limit Tests ---


class TestCheckGlobalRateLimit:
    """Tests for _check_global_rate_limit function."""

    async def test_uses_redis_when_available(self, mock_settings: MagicMock) -> None:
        """Prefers Redis rate limiting when Redis is available."""
        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="script-sha")
        mock_redis.evalsha = AsyncMock(return_value=1)  # Allowed

        with (
            patch("src.app.core.rate_limit.get_settings", return_value=mock_settings),
            patch("src.app.core.rate_limit.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_get_redis.return_value = mock_redis

            result = await rate_limit._check_global_rate_limit("test-ip")

        assert result is True
        mock_redis.evalsha.assert_called_once()

    async def test_falls_back_to_memory_when_redis_unavailable(
        self, mock_settings: MagicMock
    ) -> None:
        """Uses in-memory rate limiting when Redis is not configured."""
        with (
            patch("src.app.core.rate_limit.get_settings", return_value=mock_settings),
            patch("src.app.core.rate_limit.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_get_redis.return_value = None

            result = await rate_limit._check_global_rate_limit("fallback-ip")

        assert result is True
        # Should have created in-memory bucket
        assert "fallback-ip" in rate_limit._rate_limit_buckets

    async def test_falls_back_to_memory_on_redis_error(self, mock_settings: MagicMock) -> None:
        """Falls back to in-memory when Redis operation fails."""
        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(side_effect=Exception("Redis error"))

        with (
            patch("src.app.core.rate_limit.get_settings", return_value=mock_settings),
            patch("src.app.core.rate_limit.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_get_redis.return_value = mock_redis

            result = await rate_limit._check_global_rate_limit("error-ip")

        # Should still return a result (from in-memory fallback)
        assert result is True
        assert "error-ip" in rate_limit._rate_limit_buckets

    async def test_resets_script_sha_on_redis_error(self, mock_settings: MagicMock) -> None:
        """Script SHA is reset when Redis fails (allows re-registration)."""
        # Pre-set a script SHA
        rate_limit._script_sha = "old-sha"

        mock_redis = AsyncMock()
        mock_redis.evalsha = AsyncMock(side_effect=Exception("NOSCRIPT"))

        with (
            patch("src.app.core.rate_limit.get_settings", return_value=mock_settings),
            patch("src.app.core.rate_limit.get_redis", new_callable=AsyncMock) as mock_get_redis,
        ):
            mock_get_redis.return_value = mock_redis

            await rate_limit._check_global_rate_limit("reset-ip")

        # Script SHA should be reset after error
        assert rate_limit._script_sha is None


# --- _get_or_register_script Tests ---


class TestGetOrRegisterScript:
    """Tests for Lua script registration."""

    async def test_registers_script_on_first_call(self) -> None:
        """First call registers the Lua script with Redis."""
        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="new-sha-hash")

        sha = await rate_limit._get_or_register_script(mock_redis)

        assert sha == "new-sha-hash"
        mock_redis.script_load.assert_called_once()

    async def test_returns_cached_sha_on_subsequent_calls(self) -> None:
        """Subsequent calls return cached SHA without re-registering."""
        rate_limit._script_sha = "cached-sha"

        mock_redis = AsyncMock()
        sha = await rate_limit._get_or_register_script(mock_redis)

        assert sha == "cached-sha"
        mock_redis.script_load.assert_not_called()


# --- _check_redis_rate_limit Tests ---


class TestCheckRedisRateLimit:
    """Tests for Redis-based rate limiting."""

    async def test_returns_true_when_allowed(self, mock_settings: MagicMock) -> None:
        """Returns True when Redis script returns 1 (allowed)."""
        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="sha")
        mock_redis.evalsha = AsyncMock(return_value=1)

        with patch("src.app.core.rate_limit.get_settings", return_value=mock_settings):
            result = await rate_limit._check_redis_rate_limit(mock_redis, "test-ip")

        assert result is True

    async def test_returns_false_when_denied(self, mock_settings: MagicMock) -> None:
        """Returns False when Redis script returns 0 (rate limited)."""
        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="sha")
        mock_redis.evalsha = AsyncMock(return_value=0)

        with patch("src.app.core.rate_limit.get_settings", return_value=mock_settings):
            result = await rate_limit._check_redis_rate_limit(mock_redis, "test-ip")

        assert result is False

    async def test_uses_correct_key_format(self, mock_settings: MagicMock) -> None:
        """Redis key has correct prefix for global rate limiting."""
        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="sha")
        mock_redis.evalsha = AsyncMock(return_value=1)

        with patch("src.app.core.rate_limit.get_settings", return_value=mock_settings):
            await rate_limit._check_redis_rate_limit(mock_redis, "192.168.1.1")

        # Check the key argument (3rd positional arg after sha and numkeys)
        call_args = mock_redis.evalsha.call_args
        key_arg = call_args[0][2]  # sha, numkeys, key, ...
        assert key_arg == "global_ratelimit:192.168.1.1"

    async def test_calculates_appropriate_ttl(self, mock_settings: MagicMock) -> None:
        """TTL is calculated based on rate/burst settings."""
        mock_settings.global_rate_limit_burst = 100
        mock_settings.global_rate_limit_per_second = 10

        mock_redis = AsyncMock()
        mock_redis.script_load = AsyncMock(return_value="sha")
        mock_redis.evalsha = AsyncMock(return_value=1)

        with patch("src.app.core.rate_limit.get_settings", return_value=mock_settings):
            await rate_limit._check_redis_rate_limit(mock_redis, "ttl-test")

        # TTL should be int(burst/rate) + 60 = int(100/10) + 60 = 70
        call_args = mock_redis.evalsha.call_args
        ttl_arg = call_args[0][6]  # sha, numkeys, key, rate, burst, now, ttl
        assert ttl_arg == "70"
