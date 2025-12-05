"""Repository for EmailVerificationToken entity."""

from uuid import UUID

from sqlmodel import select, update

from src.app.models.base import utc_now
from src.app.models.public import EmailVerificationToken
from src.app.repositories.base import BaseRepository


class EmailVerificationTokenRepository(BaseRepository[EmailVerificationToken]):
    """Repository for EmailVerificationToken entity in public schema."""

    model = EmailVerificationToken

    async def get_valid_by_hash(self, token_hash: str) -> EmailVerificationToken | None:
        """Get a valid (unused, non-expired) token by its hash."""
        result = await self.session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash == token_hash,
                EmailVerificationToken.used == False,  # noqa: E712
                EmailVerificationToken.expires_at > utc_now(),
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_by_user(self, user_id: UUID) -> EmailVerificationToken | None:
        """Get the most recent token for a user."""
        result = await self.session.execute(
            select(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == user_id)
            .order_by(EmailVerificationToken.created_at.desc())  # type: ignore[attr-defined]
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def invalidate_user_tokens(self, user_id: UUID) -> None:
        """Mark all tokens for a user as used (invalidates them)."""
        await self.session.execute(
            update(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == user_id)  # type: ignore[arg-type]
            .where(EmailVerificationToken.used == False)  # type: ignore[arg-type]  # noqa: E712
            .values(used=True, used_at=utc_now())
        )

    async def mark_used(self, token: EmailVerificationToken) -> EmailVerificationToken:
        """Mark a token as used."""
        token.used = True
        token.used_at = utc_now()
        self.session.add(token)
        await self.session.flush()
        return token
