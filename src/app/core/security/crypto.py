"""Cryptographic utilities - password hashing and JWT tokens."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import argon2
from jose import JWTError, jwt

from src.app.core.config import get_settings


def _create_password_hasher() -> argon2.PasswordHasher:
    """Create password hasher with settings from config."""
    settings = get_settings()
    return argon2.PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost,
        parallelism=settings.argon2_parallelism,
    )


_password_hasher = _create_password_hasher()


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return _password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash. Returns False on any error."""
    try:
        _password_hasher.verify(hashed, password)
        return True
    except argon2.exceptions.VerifyMismatchError:
        return False
    except argon2.exceptions.InvalidHashError:
        return False


def create_access_token(
    subject: str | UUID,
    tenant_id: str | UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """Create JWT access token."""
    settings = get_settings()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode = {
        "sub": str(subject),
        "tenant_id": str(tenant_id),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(  # type: ignore[no-any-return]
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    subject: str | UUID,
    tenant_id: str | UUID,
) -> tuple[str, datetime]:
    """Create refresh token. Returns (token, expiry as naive UTC datetime)."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)

    to_encode = {
        "sub": str(subject),
        "tenant_id": str(tenant_id),
        "exp": expire,
        "type": "refresh",
    }
    token: str = jwt.encode(  # type: ignore[assignment]
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    # Return naive datetime for PostgreSQL TIMESTAMP (without timezone)
    return token, expire.replace(tzinfo=None)


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate JWT token. Returns None on any error."""
    settings = get_settings()
    try:
        return jwt.decode(  # type: ignore[no-any-return]
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None
