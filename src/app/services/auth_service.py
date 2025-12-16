"""Authentication service - handles login, token refresh (Lobby Pattern)."""

import hmac
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.cache import blacklist_token, blacklist_tokens, is_token_blacklisted
from src.app.core.config import get_settings
from src.app.core.logging import get_logger
from src.app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    verify_password,
)
from src.app.models.public import RefreshToken
from src.app.repositories import (
    MembershipRepository,
    RefreshTokenRepository,
    UserRepository,
)
from src.app.schemas.auth import LoginResponse

logger = get_logger(__name__)


class TokenType:
    """Token type constants."""

    ACCESS = "access"
    REFRESH = "refresh"
    ASSUMED_ACCESS = "assumed_access"


class AuthService:
    """Authentication service - handles login, token refresh.

    Lobby Pattern: Users are centralized in public schema.
    Login validates membership in the requested tenant.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
        membership_repo: MembershipRepository,
        session: AsyncSession,
        tenant_id: UUID,
    ):
        self.user_repo = user_repo
        self.token_repo = token_repo
        self.membership_repo = membership_repo
        self.session = session
        self.tenant_id = tenant_id

    async def authenticate(self, email: str, password: str) -> LoginResponse | None:
        """Authenticate user and return tokens.

        Validates:
        1. User exists in public.users
        2. Password is correct
        3. User is active
        4. Email is verified
        5. User has active membership in the tenant

        Returns None if authentication fails.
        Raises ValueError if email is not verified (to provide specific error).
        """
        try:
            # 1. Get user from public schema
            user = await self.user_repo.get_by_email(email)

            # 2. Verify password with constant-time comparison
            # Always perform password verification to prevent timing attacks
            # that could reveal whether an email exists in the system
            password_hash = user.hashed_password if user else DUMMY_PASSWORD_HASH
            password_valid = verify_password(password, password_hash)

            # Return None for non-existent users AFTER password check for timing safety
            if user is None:
                return None

            if not password_valid:
                return None

            # 3. Check user is active
            if not user.is_active:
                return None

            # 4. Check email is verified
            if not user.email_verified:
                raise ValueError("Email not verified")

            # 5. Verify membership in tenant
            if not await self.membership_repo.user_has_active_membership(user.id, self.tenant_id):
                return None

            # Create tokens with tenant_id (UUID)
            access_token = create_access_token(user.id, self.tenant_id)
            refresh_token, expires_at = create_refresh_token(user.id, self.tenant_id)

            # Store refresh token in public schema with tenant_id
            token_hash = hash_token(refresh_token)
            db_token = RefreshToken(
                user_id=user.id,
                tenant_id=self.tenant_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            self.token_repo.add(db_token)
            await self.session.commit()

            return LoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
            )
        except Exception:
            await self.session.rollback()
            raise

    async def refresh_access_token(self, refresh_token: str) -> tuple[str, str] | None:
        """Validate refresh token and return new access and refresh tokens.

        Implements token rotation to prevent replay attacks:
        1. Validates the refresh token
        2. Atomically revokes the old refresh token
        3. Creates new refresh and access tokens
        4. Blacklists the old token in Redis for fast rejection

        Uses Redis blacklist for fast rejection of revoked tokens.
        Falls back to database check if Redis unavailable.

        Returns:
            Tuple of (access_token, refresh_token) or None if validation fails
        """
        payload = decode_token(refresh_token)
        if payload is None:
            return None

        if payload.get("type") != TokenType.REFRESH:
            return None

        user_id = payload.get("sub")
        token_tenant_id = payload.get("tenant_id")
        if not user_id or not token_tenant_id:
            return None

        # Verify token tenant matches current tenant
        try:
            if UUID(token_tenant_id) != self.tenant_id:
                return None
        except ValueError:
            return None

        token_hash = hash_token(refresh_token)

        # Fast path: check Redis blacklist first
        blacklisted = await is_token_blacklisted(token_hash)
        if blacklisted is True:
            return None  # Token is definitely revoked

        # If blacklisted is None (Redis unavailable) or False, verify in database
        # Use FOR UPDATE to prevent TOCTOU race condition where multiple parallel
        # requests could all validate successfully before any of them revoke
        db_token = await self.token_repo.get_valid_by_hash_and_tenant(
            token_hash, self.tenant_id, for_update=True
        )

        if db_token is None:
            return None

        # Use constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(token_hash, db_token.token_hash):
            return None

        try:
            # Revoke old token BEFORE issuing new ones
            # The FOR UPDATE lock ensures only one request can proceed
            db_token.revoked = True

            # Create new refresh token with rotation
            new_refresh_token, new_expires_at = create_refresh_token(user_id, self.tenant_id)
            new_token_hash = hash_token(new_refresh_token)

            # Store new refresh token in database
            new_db_token = RefreshToken(
                user_id=UUID(user_id),
                tenant_id=self.tenant_id,
                token_hash=new_token_hash,
                expires_at=new_expires_at,
            )
            self.token_repo.add(new_db_token)

            # Commit transaction atomically - DB is source of truth
            await self.session.commit()

            # Blacklist old token in Redis AFTER successful commit
            # Redis is just a cache for fast rejection; DB remains authoritative
            try:
                settings = get_settings()
                ttl = settings.refresh_token_expire_days * 86400  # days to seconds
                await blacklist_token(token_hash, ttl)
            except Exception as e:
                # Log but don't fail - DB is already committed and authoritative
                # Token will still be rejected on DB lookup even if Redis fails
                logger.warning("Failed to blacklist token in Redis", error=str(e))

            # Create new access token
            new_access_token = create_access_token(user_id, self.tenant_id)

            return new_access_token, new_refresh_token
        except Exception:
            await self.session.rollback()
            raise

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a refresh token. Returns True if successful.

        Updates database first (source of truth), then adds token to Redis
        blacklist for fast rejection.
        """
        try:
            token_hash = hash_token(refresh_token)
            db_token = await self.token_repo.get_by_hash(token_hash)

            if db_token is None:
                return False

            # Use constant-time comparison to prevent timing attacks
            if not hmac.compare_digest(token_hash, db_token.token_hash):
                return False

            # Update database first (source of truth)
            db_token.revoked = True
            await self.session.commit()

            # Add to Redis blacklist AFTER successful commit
            # Redis is just a cache; DB remains authoritative
            try:
                settings = get_settings()
                ttl = settings.refresh_token_expire_days * 86400  # days to seconds
                await blacklist_token(token_hash, ttl)
            except Exception as e:
                # Log but don't fail - DB is already committed and authoritative
                logger.warning("Failed to blacklist token in Redis", error=str(e))

            return True
        except Exception:
            await self.session.rollback()
            raise

    async def revoke_all_tokens_for_user(self, user_id: UUID) -> int:
        """Revoke all refresh tokens for a user in the current tenant.

        Use cases:
        - Password reset (invalidate all sessions)
        - Account compromise (force re-authentication)
        - User deactivation

        Updates database first (source of truth), then adds tokens to Redis
        blacklist for fast rejection.

        Returns the number of tokens revoked.
        """
        try:
            # Get token hashes before revoking (for Redis blacklist)
            token_hashes = await self.token_repo.get_active_hashes_for_user(user_id, self.tenant_id)

            # Update database first (source of truth)
            count = await self.token_repo.revoke_all_for_user(user_id, self.tenant_id)
            await self.session.commit()

            # Bulk blacklist in Redis AFTER successful commit
            # Redis is just a cache; DB remains authoritative
            if token_hashes:
                try:
                    settings = get_settings()
                    ttl = settings.refresh_token_expire_days * 86400  # days to seconds
                    await blacklist_tokens(token_hashes, ttl)
                except Exception as e:
                    # Log but don't fail - DB is already committed and authoritative
                    logger.warning(
                        "Failed to blacklist tokens in Redis",
                        error=str(e),
                        token_count=len(token_hashes),
                    )

            return count
        except Exception:
            await self.session.rollback()
            raise
