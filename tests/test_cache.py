"""Tests for token blacklist cache module (src/app/core/cache.py)."""

from redis.asyncio import Redis

from src.app.core.cache import (
    PREFIX_TOKEN_BLACKLIST,
    blacklist_token,
    blacklist_tokens,
    is_token_blacklisted,
)


class TestBlacklistToken:
    """Tests for blacklist_token() function."""

    async def test_blacklist_token_success(self, mock_redis: Redis) -> None:
        """blacklist_token() should add token to Redis and return True."""
        token_hash = "abc123hash"
        ttl = 3600

        result = await blacklist_token(token_hash, ttl)

        assert result is True
        # Verify token is actually in Redis
        stored = await mock_redis.get(f"{PREFIX_TOKEN_BLACKLIST}:{token_hash}")
        assert stored == "1"

    async def test_blacklist_token_returns_false_when_redis_unavailable(
        self, mock_redis_unavailable: None
    ) -> None:
        """blacklist_token() should return False when Redis is unavailable."""
        result = await blacklist_token("some_hash", 3600)
        assert result is False

    async def test_blacklist_token_sets_correct_key_format(self, mock_redis: Redis) -> None:
        """blacklist_token() should use correct key format: token_blacklist:{hash}."""
        token_hash = "test_hash_123"
        await blacklist_token(token_hash, 3600)

        expected_key = f"{PREFIX_TOKEN_BLACKLIST}:{token_hash}"
        assert await mock_redis.exists(expected_key) == 1

    async def test_blacklist_token_respects_ttl(self, mock_redis: Redis) -> None:
        """blacklist_token() should set TTL on the key."""
        token_hash = "ttl_test_hash"
        ttl = 7200  # 2 hours

        await blacklist_token(token_hash, ttl)

        actual_ttl = await mock_redis.ttl(f"{PREFIX_TOKEN_BLACKLIST}:{token_hash}")
        assert actual_ttl > 0
        assert actual_ttl <= ttl


class TestIsTokenBlacklisted:
    """Tests for is_token_blacklisted() function."""

    async def test_is_token_blacklisted_returns_true_for_blacklisted(
        self, mock_redis: Redis
    ) -> None:
        """is_token_blacklisted() should return True for blacklisted tokens."""
        token_hash = "blacklisted_token"
        await blacklist_token(token_hash, 3600)

        result = await is_token_blacklisted(token_hash)
        assert result is True

    async def test_is_token_blacklisted_returns_false_for_not_blacklisted(
        self, mock_redis: Redis
    ) -> None:
        """is_token_blacklisted() should return False for tokens not in blacklist."""
        result = await is_token_blacklisted("non_existent_token")
        assert result is False

    async def test_is_token_blacklisted_returns_none_when_redis_unavailable(
        self, mock_redis_unavailable: None
    ) -> None:
        """is_token_blacklisted() should return None when Redis is unavailable.

        This signals the caller to fall back to database check.
        """
        result = await is_token_blacklisted("any_token")
        assert result is None

    async def test_three_valued_logic_distinction(self, mock_redis: Redis) -> None:
        """Verify the distinction between False (confirmed not blacklisted) and None."""
        # With Redis available, non-existent token returns False (confirmed not there)
        result = await is_token_blacklisted("not_there")
        assert result is False  # Not None - Redis confirmed it's not blacklisted


class TestBlacklistTokens:
    """Tests for blacklist_tokens() bulk operation."""

    async def test_blacklist_tokens_bulk_operation(self, mock_redis: Redis) -> None:
        """blacklist_tokens() should add multiple tokens via pipeline."""
        token_hashes = ["hash1", "hash2", "hash3", "hash4", "hash5"]
        ttl = 3600

        result = await blacklist_tokens(token_hashes, ttl)

        assert result == 5
        # Verify all tokens are blacklisted
        for token_hash in token_hashes:
            assert await is_token_blacklisted(token_hash) is True

    async def test_blacklist_tokens_empty_list(self, mock_redis: Redis) -> None:
        """blacklist_tokens() with empty list should return 0."""
        result = await blacklist_tokens([], 3600)
        assert result == 0

    async def test_blacklist_tokens_returns_zero_when_redis_unavailable(
        self, mock_redis_unavailable: None
    ) -> None:
        """blacklist_tokens() should return 0 when Redis is unavailable."""
        result = await blacklist_tokens(["hash1", "hash2"], 3600)
        assert result == 0

    async def test_blacklist_tokens_sets_ttl_on_all_keys(self, mock_redis: Redis) -> None:
        """blacklist_tokens() should set TTL on all keys."""
        token_hashes = ["ttl_hash1", "ttl_hash2"]
        ttl = 7200

        await blacklist_tokens(token_hashes, ttl)

        for token_hash in token_hashes:
            key = f"{PREFIX_TOKEN_BLACKLIST}:{token_hash}"
            actual_ttl = await mock_redis.ttl(key)
            assert actual_ttl > 0
            assert actual_ttl <= ttl


class TestTokenBlacklistIntegration:
    """Integration tests for token blacklist workflow."""

    async def test_blacklist_then_check_returns_true(self, mock_redis: Redis) -> None:
        """End-to-end: blacklist a token, then verify it's blacklisted."""
        token_hash = "integration_test_hash"

        # Initially not blacklisted
        assert await is_token_blacklisted(token_hash) is False

        # Blacklist it
        result = await blacklist_token(token_hash, 3600)
        assert result is True

        # Now should be blacklisted
        assert await is_token_blacklisted(token_hash) is True

    async def test_multiple_tokens_independent(self, mock_redis: Redis) -> None:
        """Blacklisting one token should not affect others."""
        token1 = "independent_token_1"
        token2 = "independent_token_2"

        # Blacklist only token1
        await blacklist_token(token1, 3600)

        # token1 should be blacklisted, token2 should not
        assert await is_token_blacklisted(token1) is True
        assert await is_token_blacklisted(token2) is False

    async def test_bulk_blacklist_workflow(self, mock_redis: Redis) -> None:
        """Simulate revoking all tokens for a user."""
        user_tokens = ["user1_token_a", "user1_token_b", "user1_token_c"]
        other_user_token = "user2_token"

        # Blacklist user1's tokens in bulk
        await blacklist_tokens(user_tokens, 3600)

        # All user1 tokens should be blacklisted
        for token in user_tokens:
            assert await is_token_blacklisted(token) is True

        # user2's token should not be affected
        assert await is_token_blacklisted(other_user_token) is False

    async def test_key_prefix_isolation(self, mock_redis: Redis) -> None:
        """Verify token blacklist keys are properly namespaced."""
        token_hash = "isolation_test"

        # Set a key with different prefix (simulating other cache data)
        await mock_redis.set("other_prefix:isolation_test", "other_value")

        # Blacklist the token
        await blacklist_token(token_hash, 3600)

        # Both keys should exist independently
        assert await mock_redis.get("other_prefix:isolation_test") == "other_value"
        assert await mock_redis.get(f"{PREFIX_TOKEN_BLACKLIST}:{token_hash}") == "1"

        # is_token_blacklisted should only check the blacklist prefix
        assert await is_token_blacklisted(token_hash) is True
