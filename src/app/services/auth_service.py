"""Authentication service - handles login, token refresh (Lobby Pattern)."""

import hmac
from hashlib import sha256
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.cache import blacklist_token, blacklist_tokens, is_token_blacklisted
from src.app.core.config import get_settings
from src.app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from src.app.models.public import RefreshToken
from src.app.repositories import (
    MembershipRepository,
    RefreshTokenRepository,
    UserRepository,
)
from src.app.schemas.auth import LoginResponse


class TokenType:
    """Token type constants."""

    ACCESS = "access"
    REFRESH = "refresh"


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
            if user is None:
                return None

            # 2. Verify password
            if not verify_password(password, user.hashed_password):
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
            token_hash = sha256(refresh_token.encode()).hexdigest()
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

    async def refresh_access_token(self, refresh_token: str) -> str | None:
        """Validate refresh token and return new access token.

        Uses Redis blacklist for fast rejection of revoked tokens.
        Falls back to database check if Redis unavailable.
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

        token_hash = sha256(refresh_token.encode()).hexdigest()

        # Fast path: check Redis blacklist first
        blacklisted = await is_token_blacklisted(token_hash)
        if blacklisted is True:
            return None  # Token is definitely revoked

        # If blacklisted is None (Redis unavailable) or False, verify in database
        db_token = await self.token_repo.get_valid_by_hash_and_tenant(token_hash, self.tenant_id)

        if db_token is None:
            return None

        # Use constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(token_hash, db_token.token_hash):
            return None

        return create_access_token(user_id, self.tenant_id)

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a refresh token. Returns True if successful.

        Adds token to Redis blacklist for fast rejection and updates
        database as source of truth.
        """
        try:
            token_hash = sha256(refresh_token.encode()).hexdigest()
            db_token = await self.token_repo.get_by_hash(token_hash)

            if db_token is None:
                return False

            # Use constant-time comparison to prevent timing attacks
            if not hmac.compare_digest(token_hash, db_token.token_hash):
                return False

            # Add to Redis blacklist (if available) for fast rejection
            settings = get_settings()
            ttl = settings.refresh_token_expire_days * 86400  # days to seconds
            await blacklist_token(token_hash, ttl)

            # Always update database (source of truth)
            db_token.revoked = True
            await self.session.commit()
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

        Adds all tokens to Redis blacklist for fast rejection and updates
        database as source of truth.

        Returns the number of tokens revoked.
        """
        try:
            # Get token hashes before revoking (for Redis blacklist)
            token_hashes = await self.token_repo.get_active_hashes_for_user(user_id, self.tenant_id)

            # Bulk blacklist in Redis (if available)
            if token_hashes:
                settings = get_settings()
                ttl = settings.refresh_token_expire_days * 86400  # days to seconds
                await blacklist_tokens(token_hashes, ttl)

            # Always update database (source of truth)
            count = await self.token_repo.revoke_all_for_user(user_id, self.tenant_id)
            await self.session.commit()
            return count
        except Exception:
            await self.session.rollback()
            raise
