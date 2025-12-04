"""Authentication service - handles login, token refresh, registration."""

from hashlib import sha256

from src.app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.app.models.tenant import RefreshToken, User
from src.app.repositories.token_repository import RefreshTokenRepository
from src.app.repositories.user_repository import UserRepository
from src.app.schemas.auth import LoginResponse


class TokenType:
    """Token type constants."""

    ACCESS = "access"
    REFRESH = "refresh"


class AuthService:
    """Authentication service - handles login, token refresh, registration."""

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
        tenant_id: str,
    ):
        self.user_repo = user_repo
        self.token_repo = token_repo
        self.tenant_id = tenant_id

    async def authenticate(self, email: str, password: str) -> LoginResponse | None:
        """Authenticate user and return tokens. Returns None if authentication fails."""
        user = await self.user_repo.get_by_email(email)

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
        await self.token_repo.add(db_token)
        await self.token_repo.commit()

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def refresh_access_token(self, refresh_token: str) -> str | None:
        """Validate refresh token and return new access token."""
        payload = decode_token(refresh_token)
        if payload is None:
            return None

        if payload.get("type") != TokenType.REFRESH:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        token_hash = sha256(refresh_token.encode()).hexdigest()
        db_token = await self.token_repo.get_valid_by_hash(token_hash)

        if db_token is None:
            return None

        return create_access_token(user_id, self.tenant_id)

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a refresh token. Returns True if successful."""
        token_hash = sha256(refresh_token.encode()).hexdigest()
        db_token = await self.token_repo.get_by_hash(token_hash)

        if db_token is None:
            return False

        db_token.revoked = True
        await self.token_repo.commit()
        return True

    async def register_user(
        self,
        email: str,
        password: str,
        full_name: str,
    ) -> User | None:
        """Register new user. Returns None if email already exists."""
        if await self.user_repo.exists_by_email(email):
            return None

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
        )
        await self.user_repo.add(user)
        await self.user_repo.commit()

        return user
