"""Authentication-related factories for test data generation."""

import secrets
from datetime import timedelta
from hashlib import sha256
from uuid import UUID

from polyfactory import Use

from src.app.models.enums import InviteStatus, MembershipRole
from src.app.models.public import EmailVerificationToken, RefreshToken, TenantInvite
from tests.factories.base import BaseFactory, generate_uuid7, utc_now


def generate_token_hash() -> str:
    """Generate a random token hash."""
    return sha256(secrets.token_urlsafe(32).encode()).hexdigest()


class RefreshTokenFactory(BaseFactory):
    """Factory for generating RefreshToken test data."""

    __model__ = RefreshToken

    id = Use(generate_uuid7)
    user_id = None  # Required FK - must be set explicitly
    tenant_id = None  # Required FK - must be set explicitly
    token_hash = Use(generate_token_hash)
    expires_at = Use(lambda: utc_now() + timedelta(days=7))
    created_at = Use(utc_now)
    revoked = False

    @classmethod
    def revoked_token(cls, **kwargs):
        """Create a revoked token."""
        return cls.build(revoked=True, **kwargs)

    @classmethod
    def expired(cls, **kwargs):
        """Create an expired token."""
        return cls.build(expires_at=utc_now() - timedelta(days=1), **kwargs)


class EmailVerificationTokenFactory(BaseFactory):
    """Factory for generating EmailVerificationToken test data."""

    __model__ = EmailVerificationToken

    id = Use(generate_uuid7)
    user_id = None  # Required FK - must be set explicitly
    token_hash = Use(generate_token_hash)
    expires_at = Use(lambda: utc_now() + timedelta(hours=24))
    created_at = Use(utc_now)
    used = False
    used_at = None

    @classmethod
    def used_token(cls, **kwargs):
        """Create a used verification token."""
        return cls.build(used=True, used_at=utc_now(), **kwargs)

    @classmethod
    def expired(cls, **kwargs):
        """Create an expired verification token."""
        return cls.build(expires_at=utc_now() - timedelta(hours=1), **kwargs)


class TenantInviteFactory(BaseFactory):
    """Factory for generating TenantInvite test data."""

    __model__ = TenantInvite

    id = Use(generate_uuid7)
    tenant_id = None  # Required FK - must be set explicitly
    email = Use(lambda: f"invite_{generate_uuid7().hex[-8:]}@example.com")
    token_hash = Use(generate_token_hash)
    role = MembershipRole.MEMBER.value
    invited_by_user_id = None  # Required FK - must be set explicitly
    status = InviteStatus.PENDING.value
    expires_at = Use(lambda: utc_now() + timedelta(days=7))
    created_at = Use(utc_now)
    accepted_at = None
    accepted_by_user_id = None

    @classmethod
    def accepted(cls, accepted_by: UUID, **kwargs):
        """Create an accepted invite."""
        return cls.build(
            status=InviteStatus.ACCEPTED.value,
            accepted_at=utc_now(),
            accepted_by_user_id=accepted_by,
            **kwargs,
        )

    @classmethod
    def cancelled(cls, **kwargs):
        """Create a cancelled invite."""
        return cls.build(status=InviteStatus.CANCELLED.value, **kwargs)

    @classmethod
    def expired(cls, **kwargs):
        """Create an expired invite."""
        return cls.build(
            status=InviteStatus.EXPIRED.value,
            expires_at=utc_now() - timedelta(days=1),
            **kwargs,
        )

    @classmethod
    def admin_role(cls, **kwargs):
        """Create an invite with admin role."""
        return cls.build(role=MembershipRole.ADMIN.value, **kwargs)
