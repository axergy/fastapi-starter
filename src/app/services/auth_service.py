from hashlib import sha256

from src.app.models.base import utc_now

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.app.models.tenant import RefreshToken, User
from src.app.schemas.auth import LoginResponse


class AuthService:
    """Authentication service - handles login, token refresh, registration."""

    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    async def authenticate(self, email: str, password: str) -> LoginResponse | None:
        """Authenticate user and return tokens. Returns None if authentication fails."""
        result = await self.session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            return None

        access_token = create_access_token(user.id, self.tenant_id)
        refresh_token, expires_at = create_refresh_token(user.id, self.tenant_id)

        token_hash = sha256(refresh_token.encode()).hexdigest()
        db_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(db_token)
        await self.session.commit()

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def refresh_access_token(self, refresh_token: str) -> str | None:
        """Validate refresh token and return new access token."""
        payload = decode_token(refresh_token)
        if payload is None:
            return None

        if payload.get("type") != "refresh":
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        token_hash = sha256(refresh_token.encode()).hexdigest()
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked == False,  # noqa: E712
                RefreshToken.expires_at > utc_now(),
            )
        )
        db_token = result.scalar_one_or_none()

        if db_token is None:
            return None

        return create_access_token(user_id, self.tenant_id)

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a refresh token. Returns True if successful."""
        token_hash = sha256(refresh_token.encode()).hexdigest()
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        db_token = result.scalar_one_or_none()

        if db_token is None:
            return False

        db_token.revoked = True
        await self.session.commit()
        return True

    async def register_user(
        self,
        email: str,
        password: str,
        full_name: str,
    ) -> User | None:
        """Register new user. Returns None if email already exists."""
        result = await self.session.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none() is not None:
            return None

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        return user
