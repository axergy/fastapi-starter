"""Repository for RefreshToken entity."""

from sqlmodel import select

from src.app.models.base import utc_now
from src.app.models.tenant import RefreshToken
from src.app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Repository for RefreshToken entity."""

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
