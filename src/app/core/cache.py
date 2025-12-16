"""Token blacklist service with Redis backend and graceful fallback.

This module provides fast token revocation checks using Redis.
When Redis is unavailable, callers should fall back to database checks.
"""

from src.app.core.redis import get_redis

PREFIX_TOKEN_BLACKLIST = "token_blacklist"


async def blacklist_token(token_hash: str, ttl: int) -> bool:
    """Add token to blacklist (for revoked tokens).

    Args:
        token_hash: SHA256 hash of the token to blacklist
        ttl: Time-to-live in seconds (should match token expiry)

    Returns:
        True if successfully added to Redis, False if Redis unavailable
    """
    redis = await get_redis()
    if not redis:
        return False
    await redis.setex(f"{PREFIX_TOKEN_BLACKLIST}:{token_hash}", ttl, "1")
    return True


async def is_token_blacklisted(token_hash: str) -> bool | None:
    """Check if token is in the blacklist.

    Returns:
        True: Token is blacklisted (revoked)
        False: Token is NOT blacklisted (Redis confirmed it's not there)
        None: Redis unavailable (caller must check database)
    """
    redis = await get_redis()
    if not redis:
        return None  # Caller must fall back to DB
    result = await redis.get(f"{PREFIX_TOKEN_BLACKLIST}:{token_hash}")
    return result is not None


async def blacklist_tokens(token_hashes: list[str], ttl: int) -> int:
    """Bulk blacklist multiple tokens.

    Used when revoking all tokens for a user.

    Args:
        token_hashes: List of SHA256 hashes to blacklist
        ttl: Time-to-live in seconds

    Returns:
        Number of tokens successfully blacklisted (0 if Redis unavailable)
    """
    redis = await get_redis()
    if not redis:
        return 0

    # Use pipeline for efficiency
    pipe = redis.pipeline()
    for token_hash in token_hashes:
        pipe.setex(f"{PREFIX_TOKEN_BLACKLIST}:{token_hash}", ttl, "1")
    await pipe.execute()
    return len(token_hashes)


async def blacklist_tokens_with_ttls(tokens_with_ttls: list[tuple[str, int]]) -> int:
    """Bulk blacklist multiple tokens with individual TTLs.

    Used when revoking all tokens for a user with proper remaining TTLs.

    Args:
        tokens_with_ttls: List of (token_hash, ttl) tuples

    Returns:
        Number of tokens successfully blacklisted (0 if Redis unavailable)
    """
    redis = await get_redis()
    if not redis:
        return 0

    # Use pipeline for efficiency
    pipe = redis.pipeline()
    for token_hash, ttl in tokens_with_ttls:
        if ttl > 0:  # Only blacklist if TTL is positive
            pipe.setex(f"{PREFIX_TOKEN_BLACKLIST}:{token_hash}", ttl, "1")
    await pipe.execute()
    return len(tokens_with_ttls)
