"""Test helper functions for common data creation patterns."""

import secrets
from hashlib import sha256

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models.enums import MembershipRole
from src.app.models.public import Tenant, TenantInvite, User, UserTenantMembership
from tests.factories import (
    TenantFactory,
    TenantInviteFactory,
    UserFactory,
    UserTenantMembershipFactory,
)


async def create_user_with_membership(
    session: AsyncSession,
    tenant: Tenant,
    role: MembershipRole = MembershipRole.ADMIN,
    **user_kwargs,
) -> tuple[User, UserTenantMembership]:
    """Create a user and their membership in a tenant.

    Args:
        session: Database session
        tenant: Tenant to create membership in
        role: Role for the membership (default: ADMIN)
        **user_kwargs: Additional args passed to UserFactory

    Returns:
        Tuple of (user, membership)
    """
    user = UserFactory.build(**user_kwargs)
    session.add(user)
    await session.flush()

    membership = UserTenantMembershipFactory.build(
        user_id=user.id,
        tenant_id=tenant.id,
        role=role.value,
    )
    session.add(membership)
    await session.flush()

    return user, membership


async def create_superuser_with_membership(
    session: AsyncSession,
    tenant: Tenant,
    **user_kwargs,
) -> tuple[User, UserTenantMembership]:
    """Create a superuser with admin membership in a tenant.

    Args:
        session: Database session
        tenant: Tenant to create membership in
        **user_kwargs: Additional args passed to UserFactory

    Returns:
        Tuple of (superuser, membership)
    """
    return await create_user_with_membership(
        session,
        tenant,
        role=MembershipRole.ADMIN,
        is_superuser=True,
        full_name=user_kwargs.pop("full_name", "Super User"),
        **user_kwargs,
    )


async def create_tenant(
    session: AsyncSession,
    **tenant_kwargs,
) -> Tenant:
    """Create a tenant.

    Args:
        session: Database session
        **tenant_kwargs: Args passed to TenantFactory

    Returns:
        Created tenant
    """
    tenant = TenantFactory.build(**tenant_kwargs)
    session.add(tenant)
    await session.flush()
    return tenant


async def create_invite_with_inviter(
    session: AsyncSession,
    tenant: Tenant,
    **invite_kwargs,
) -> tuple[TenantInvite, User, str]:
    """Create a tenant invite with its inviter user.

    Args:
        session: Database session
        tenant: Tenant the invite is for
        **invite_kwargs: Additional args passed to TenantInviteFactory

    Returns:
        Tuple of (invite, inviter_user, plaintext_token)
    """
    # Create inviter user
    inviter = UserFactory.build()
    session.add(inviter)
    await session.flush()

    # Generate token
    token = secrets.token_urlsafe(32)
    token_hash = sha256(token.encode()).hexdigest()

    # Create invite
    invite = TenantInviteFactory.build(
        tenant_id=tenant.id,
        invited_by_user_id=inviter.id,
        token_hash=token_hash,
        **invite_kwargs,
    )
    session.add(invite)
    await session.flush()

    return invite, inviter, token


async def create_full_test_scenario(
    session: AsyncSession,
) -> dict:
    """Create a complete test scenario with tenant, admin user, and membership.

    Returns:
        Dict with keys: tenant, user, membership, password
    """
    from tests.factories import DEFAULT_TEST_PASSWORD

    tenant = await create_tenant(session)
    user, membership = await create_user_with_membership(session, tenant)

    return {
        "tenant": tenant,
        "user": user,
        "membership": membership,
        "password": DEFAULT_TEST_PASSWORD,
    }
