"""Repository for RefreshToken entity."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, delete, or_, update
from sqlmodel import select

from src.app.models.base import utc_now
from src.app.models.public import RefreshToken
from src.app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Repository for RefreshToken entity in public schema (Lobby Pattern)."""

    model = RefreshToken

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Get refresh token by its hash."""
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_hash_and_tenant(self, token_hash: str, tenant_id: UUID) -> RefreshToken | None:
        """Get refresh token by hash, scoped to tenant.

        Args:
            token_hash: The hashed token to look up
            tenant_id: The tenant ID to scope the search
        """
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_valid_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Get a valid (non-revoked, non-expired) refresh token by hash."""
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked == False,  # noqa: E712
                RefreshToken.expires_at > utc_now(),
            )
        )
        return result.scalar_one_or_none()

    async def get_valid_by_hash_and_tenant(
        self, token_hash: str, tenant_id: UUID, for_update: bool = False
    ) -> RefreshToken | None:
        """Get a valid refresh token by hash, scoped to tenant.

        Args:
            token_hash: The hashed token to look up
            tenant_id: The tenant ID to scope the search
            for_update: If True, locks the row to prevent TOCTOU race conditions
                       during token refresh operations
        """
        query = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.tenant_id == tenant_id,
            RefreshToken.revoked == False,  # noqa: E712
            RefreshToken.expires_at > utc_now(),
        )
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_hashes_for_user(self, user_id: UUID, tenant_id: UUID) -> list[str]:
        """Get token hashes for all active tokens of a user in a tenant.

        Used for bulk blacklisting in Redis cache.
        """
        result = await self.session.execute(
            select(RefreshToken.token_hash).where(
                RefreshToken.user_id == user_id,
                RefreshToken.tenant_id == tenant_id,
                RefreshToken.revoked == False,  # noqa: E712
                RefreshToken.expires_at > utc_now(),
            )
        )
        return list(result.scalars().all())

    async def get_active_tokens_for_user(
        self, user_id: UUID, tenant_id: UUID
    ) -> list[RefreshToken]:
        """Get all active tokens of a user in a tenant with full token data.

        Used for bulk blacklisting in Redis cache with proper TTLs.
        """
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.tenant_id == tenant_id,
                RefreshToken.revoked == False,  # noqa: E712
                RefreshToken.expires_at > utc_now(),
            )
        )
        return list(result.scalars().all())

    async def revoke_all_for_user(self, user_id: UUID, tenant_id: UUID) -> int:
        """Revoke all active refresh tokens for a user in a tenant.

        Returns the number of tokens revoked.
        """
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)  # type: ignore[arg-type]
            .where(RefreshToken.tenant_id == tenant_id)  # type: ignore[arg-type]
            .where(RefreshToken.revoked == False)  # type: ignore[arg-type]  # noqa: E712
            .values(revoked=True)
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def cleanup_expired(self, retention_days: int) -> int:
        """Delete tokens expired more than retention_days ago.

        Also deletes revoked tokens older than retention_days.
        Idempotent: DELETE operations are inherently idempotent.

        Args:
            retention_days: Number of days to retain expired/revoked tokens

        Returns:
            Number of tokens deleted
        """
        cutoff = utc_now() - timedelta(days=retention_days)
        stmt = delete(RefreshToken).where(
            or_(
                RefreshToken.expires_at < cutoff,  # type: ignore[arg-type]
                and_(
                    RefreshToken.revoked == True,  # type: ignore[arg-type]  # noqa: E712
                    RefreshToken.created_at < cutoff,  # type: ignore[arg-type]
                ),
            )
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0  # type: ignore[attr-defined]
