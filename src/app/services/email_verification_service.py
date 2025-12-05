"""Email verification service."""

import secrets
from datetime import timedelta
from hashlib import sha256

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.config import get_settings
from src.app.core.logging import get_logger
from src.app.core.notifications import send_verification_email, send_welcome_email
from src.app.models.base import utc_now
from src.app.models.public import EmailVerificationToken, User
from src.app.repositories import EmailVerificationTokenRepository, UserRepository

logger = get_logger(__name__)


class EmailVerificationService:
    """Service for email verification operations.

    Handles token generation, validation, and email sending.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: EmailVerificationTokenRepository,
        session: AsyncSession,
    ):
        self.user_repo = user_repo
        self.token_repo = token_repo
        self.session = session

    async def create_and_send_verification(self, user: User) -> str | None:
        """Create verification token and send email.

        Args:
            user: User to send verification email to

        Returns:
            The plaintext token (for dev/testing), or None on failure
        """
        settings = get_settings()

        try:
            # Invalidate any existing tokens for this user
            await self.token_repo.invalidate_user_tokens(user.id)

            # Generate cryptographically secure token
            token = secrets.token_urlsafe(32)
            token_hash = sha256(token.encode()).hexdigest()

            # Calculate expiry
            expires_at = utc_now() + timedelta(hours=settings.email_verification_expire_hours)

            # Store token
            db_token = EmailVerificationToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            self.token_repo.add(db_token)
            await self.session.commit()

            # Send email (non-blocking in terms of transaction)
            send_verification_email(user.email, token, user.full_name)

            logger.info("Verification email sent", user_id=str(user.id), email=user.email)
            return token

        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to create verification token", error=str(e))
            raise

    async def verify_token(self, token: str) -> User | None:
        """Verify email token and mark user as verified.

        Args:
            token: The plaintext verification token

        Returns:
            The verified User, or None if invalid/expired
        """
        try:
            token_hash = sha256(token.encode()).hexdigest()
            db_token = await self.token_repo.get_valid_by_hash(token_hash)

            if db_token is None:
                logger.warning("Invalid or expired verification token")
                return None

            # Get user
            user = await self.user_repo.get_by_id(db_token.user_id)
            if user is None:
                logger.warning(
                    "User not found for verification token", user_id=str(db_token.user_id)
                )
                return None

            # Already verified?
            if user.email_verified:
                logger.info("User already verified", user_id=str(user.id))
                # Still mark token as used to prevent reuse
                await self.token_repo.mark_used(db_token)
                await self.session.commit()
                return user

            # Mark user as verified
            user.email_verified = True
            user.email_verified_at = utc_now()
            self.session.add(user)

            # Mark token as used
            await self.token_repo.mark_used(db_token)

            await self.session.commit()

            # Send welcome email
            send_welcome_email(user.email, user.full_name)

            logger.info("User email verified", user_id=str(user.id))
            return user

        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to verify token", error=str(e))
            raise

    async def resend_verification(self, email: str) -> bool:
        """Resend verification email to user.

        Args:
            email: Email address to resend to

        Returns:
            True if sent (or user not found - to prevent enumeration),
            False on actual error
        """
        try:
            user = await self.user_repo.get_by_email(email)

            # Always return True to prevent email enumeration
            if user is None:
                logger.info("Resend requested for non-existent email", email=email)
                return True

            # Already verified
            if user.email_verified:
                logger.info("Resend requested for already verified user", user_id=str(user.id))
                return True

            # Create and send new token
            await self.create_and_send_verification(user)
            return True

        except Exception as e:
            logger.error("Failed to resend verification", error=str(e))
            return False
