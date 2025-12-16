"""Cryptographic utilities - password hashing, JWT tokens, and token hashing."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid7

import argon2
from jose import JWTError, jwt

from src.app.core.config import get_settings


def hash_token(token: str) -> str:
    """Hash a token using SHA256 for secure storage."""
    return sha256(token.encode()).hexdigest()


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
    """Create refresh token. Returns (token, expiry as naive UTC datetime).

    Includes a unique JWT ID (jti) to ensure each token is unique, even if created
    in the same second for the same user. This is crucial for token rotation.
    """
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)

    to_encode = {
        "sub": str(subject),
        "tenant_id": str(tenant_id),
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid7()),  # Unique ID for each token to prevent hash collisions
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


# Default expiry for assumed identity tokens (shorter than regular access tokens)
ASSUMED_IDENTITY_TOKEN_EXPIRE_MINUTES = 15


def create_assumed_identity_token(
    assumed_user_id: str | UUID,
    operator_user_id: str | UUID,
    tenant_id: str | UUID,
    reason: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create JWT token for an assumed identity session.

    This token allows a superuser (operator) to act as another user (assumed).
    The token structure is compatible with regular access tokens but includes
    additional claims to identify the assumed identity session.

    Args:
        assumed_user_id: The user whose identity is being assumed (becomes 'sub')
        operator_user_id: The superuser performing the assumption
        tenant_id: Target tenant context for the session
        reason: Optional reason for the assumption (for audit purposes)
        expires_delta: Token expiry (defaults to 15 minutes)

    Returns:
        JWT token string
    """
    settings = get_settings()

    # Shorter default expiry for assumed identity tokens (15 minutes)
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ASSUMED_IDENTITY_TOKEN_EXPIRE_MINUTES)

    started_at = datetime.now(UTC)

    to_encode = {
        "sub": str(assumed_user_id),
        "tenant_id": str(tenant_id),
        "exp": expire,
        "type": "access",
        "assumed_identity": {
            "operator_user_id": str(operator_user_id),
            "reason": reason,
            "started_at": started_at.isoformat(),
        },
    }
    return jwt.encode(  # type: ignore[no-any-return]
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
