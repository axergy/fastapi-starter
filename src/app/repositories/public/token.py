"""Repository for RefreshToken entity."""

from uuid import UUID

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
        self, token_hash: str, tenant_id: UUID
    ) -> RefreshToken | None:
        """Get a valid refresh token by hash, scoped to tenant."""
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.tenant_id == tenant_id,
                RefreshToken.revoked == False,  # noqa: E712
                RefreshToken.expires_at > utc_now(),
            )
        )
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

    async def revoke_all_for_user(self, user_id: UUID, tenant_id: UUID) -> int:
        """Revoke all active refresh tokens for a user in a tenant.

        Returns the number of tokens revoked.
        """
        from sqlalchemy import update

        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)  # type: ignore[arg-type]
            .where(RefreshToken.tenant_id == tenant_id)  # type: ignore[arg-type]
            .where(RefreshToken.revoked == False)  # type: ignore[arg-type]  # noqa: E712
            .values(revoked=True)
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0  # type: ignore[attr-defined]
