"""User and membership factories for test data generation."""

from polyfactory import Use

from src.app.core.security import hash_password
from src.app.models.enums import MembershipRole
from src.app.models.public import User, UserTenantMembership
from tests.factories.base import BaseFactory, generate_uuid7, utc_now

# Default test password - stored for convenience in tests
DEFAULT_TEST_PASSWORD = "testpassword123"


class UserFactory(BaseFactory):
    """Factory for generating User test data."""

    __model__ = User

    id = Use(generate_uuid7)
    email = Use(lambda: f"user_{generate_uuid7().hex[-8:]}@example.com")
    hashed_password = Use(lambda: hash_password(DEFAULT_TEST_PASSWORD))
    full_name = "Test User"
    is_active = True
    is_superuser = False
    email_verified = True
    email_verified_at = Use(utc_now)
    created_at = Use(utc_now)
    updated_at = Use(utc_now)

    @classmethod
    def superuser(cls, **kwargs):
        """Create a superuser."""
        return cls.build(
            is_superuser=True,
            full_name=kwargs.pop("full_name", "Super User"),
            **kwargs,
        )

    @classmethod
    def unverified(cls, **kwargs):
        """Create an unverified user."""
        return cls.build(email_verified=False, email_verified_at=None, **kwargs)

    @classmethod
    def inactive(cls, **kwargs):
        """Create an inactive user."""
        return cls.build(is_active=False, **kwargs)


class UserTenantMembershipFactory(BaseFactory):
    """Factory for generating UserTenantMembership test data."""

    __model__ = UserTenantMembership

    # FK fields - must be set explicitly
    user_id = None
    tenant_id = None
    role = MembershipRole.ADMIN.value
    is_active = True
    created_at = Use(utc_now)

    @classmethod
    def member(cls, **kwargs):
        """Create a member role membership."""
        return cls.build(role=MembershipRole.MEMBER.value, **kwargs)

    @classmethod
    def admin(cls, **kwargs):
        """Create an admin role membership."""
        return cls.build(role=MembershipRole.ADMIN.value, **kwargs)
