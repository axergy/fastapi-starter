"""Token and invite cleanup activities."""

from temporalio import activity

from src.app.core.db import get_public_session


@activity.defn
async def cleanup_refresh_tokens(retention_days: int) -> int:
    """
    Clean up expired refresh tokens.

    Deletes tokens that:
    - Expired more than retention_days ago, OR
    - Were revoked and created more than retention_days ago

    Idempotent: DELETE operations are inherently idempotent - running multiple
    times will not cause side effects. Second run finds no matching records.

    Args:
        retention_days: Number of days to retain expired/revoked tokens

    Returns:
        Number of tokens deleted
    """
    activity.logger.info(f"Cleaning up refresh tokens older than {retention_days} days")

    async with get_public_session() as session:
        from src.app.repositories.public.token import RefreshTokenRepository

        repo = RefreshTokenRepository(session)
        count = await repo.cleanup_expired(retention_days)

    activity.logger.info(f"Deleted {count} expired refresh tokens")
    return count


@activity.defn
async def cleanup_email_verification_tokens(retention_days: int) -> int:
    """
    Clean up expired email verification tokens.

    Deletes tokens that:
    - Expired more than retention_days ago, OR
    - Were used and created more than retention_days ago

    Idempotent: DELETE operations are inherently idempotent.

    Args:
        retention_days: Number of days to retain expired/used tokens

    Returns:
        Number of tokens deleted
    """
    activity.logger.info(f"Cleaning up email verification tokens older than {retention_days} days")

    async with get_public_session() as session:
        from src.app.repositories.public.email_verification import (
            EmailVerificationTokenRepository,
        )

        repo = EmailVerificationTokenRepository(session)
        count = await repo.cleanup_expired(retention_days)

    activity.logger.info(f"Deleted {count} expired email verification tokens")
    return count


@activity.defn
async def cleanup_expired_invites(retention_days: int) -> int:
    """
    Clean up expired tenant invites.

    Deletes invites that:
    - Expired more than retention_days ago, OR
    - Were cancelled/accepted and created more than retention_days ago

    Idempotent: DELETE operations are inherently idempotent.

    Args:
        retention_days: Number of days to retain expired/cancelled/accepted invites

    Returns:
        Number of invites deleted
    """
    activity.logger.info(f"Cleaning up tenant invites older than {retention_days} days")

    async with get_public_session() as session:
        from src.app.repositories.public.invite import TenantInviteRepository

        repo = TenantInviteRepository(session)
        count = await repo.cleanup_expired(retention_days)

    activity.logger.info(f"Deleted {count} expired tenant invites")
    return count
