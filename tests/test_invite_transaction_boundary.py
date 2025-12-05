"""Tests for TODO #002: Missing Transaction Boundary in Accept Invite Flow.

This test suite validates that:
1. Tenant validation happens WITHIN the transaction
2. Deleted tenants are properly rejected
3. No race condition exists between commit and tenant retrieval
"""

import secrets
from hashlib import sha256
from uuid import uuid7

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.app.core.security import hash_password


@pytest.fixture
async def invite_token_and_tenant(engine: AsyncEngine, test_tenant: str) -> tuple[str, str, str]:
    """Create an invite token for testing.

    Returns (token, invite_email, tenant_id).
    """
    invite_email = f"invite_{uuid7().hex[-8:]}@example.com"
    token = secrets.token_urlsafe(32)
    token_hash = sha256(token.encode()).hexdigest()

    async with engine.connect() as conn:
        # Get tenant_id
        result = await conn.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        tenant_id = str(result.scalar_one())

        # Create invite
        await conn.execute(
            text(
                """
                INSERT INTO public.tenant_invites
                (id, tenant_id, email, token_hash, role, status,
                 invited_by_user_id, expires_at, created_at)
                VALUES (gen_random_uuid(), :tenant_id, :email, :token_hash,
                 'member', 'pending', NULL, now() + interval '7 days', now())
                """
            ),
            {
                "tenant_id": tenant_id,
                "email": invite_email,
                "token_hash": token_hash,
            },
        )
        await conn.commit()

    yield token, invite_email, tenant_id

    # Cleanup (invite will be cleaned by test_tenant fixture)


@pytest.mark.asyncio
async def test_accept_invite_deleted_tenant_existing_user(
    engine: AsyncEngine,
    test_tenant: str,
    invite_token_and_tenant: tuple[str, str, str],
):
    """Test that accepting an invite for a deleted tenant fails (existing user flow).

    This validates that the tenant check happens WITHIN the transaction,
    preventing the race condition where tenant is deleted after invite is accepted.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.app.models.public import User
    from src.app.repositories import (
        MembershipRepository,
        TenantInviteRepository,
        TenantRepository,
        UserRepository,
    )
    from src.app.services.invite_service import InviteService

    token, invite_email, tenant_id = invite_token_and_tenant

    # Create a user with the invite's email
    user_id = uuid7()
    async with engine.connect() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO public.users
                (id, email, hashed_password, full_name, is_active, is_superuser,
                 email_verified, email_verified_at, created_at, updated_at)
                VALUES (:id, :email, :hashed_password, :full_name, true, false,
                 true, now(), now(), now())
                """
            ),
            {
                "id": user_id,
                "email": invite_email,
                "hashed_password": hash_password("password123"),
                "full_name": "Test User",
            },
        )

        # SOFT-DELETE the tenant (set deleted_at)
        await conn.execute(
            text("UPDATE public.tenants SET deleted_at = now() WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        await conn.commit()

    # Try to accept invite - should fail with tenant validation error
    async with AsyncSession(engine) as session:
        user = await session.get(User, user_id)

        invite_repo = TenantInviteRepository(session)
        user_repo = UserRepository(session)
        membership_repo = MembershipRepository(session)
        tenant_repo = TenantRepository(session)

        invite_service = InviteService(
            invite_repo=invite_repo,
            user_repo=user_repo,
            membership_repo=membership_repo,
            tenant_repo=tenant_repo,
            session=session,
        )

        with pytest.raises(ValueError, match="Tenant is no longer available"):
            await invite_service.accept_invite_existing_user(token, user)

    # Cleanup user
    async with engine.connect() as conn:
        await conn.execute(
            text("DELETE FROM public.users WHERE id = :id"),
            {"id": user_id},
        )
        # Un-delete tenant for cleanup
        await conn.execute(
            text("UPDATE public.tenants SET deleted_at = NULL WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_accept_invite_deleted_tenant_new_user(
    engine: AsyncEngine,
    test_tenant: str,
    invite_token_and_tenant: tuple[str, str, str],
):
    """Test that accepting an invite for a deleted tenant fails (new user flow).

    This validates that the tenant check happens WITHIN the transaction,
    preventing the race condition where tenant is deleted after user is created.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.app.repositories import (
        MembershipRepository,
        TenantInviteRepository,
        TenantRepository,
        UserRepository,
    )
    from src.app.services.invite_service import InviteService

    token, invite_email, tenant_id = invite_token_and_tenant

    # SOFT-DELETE the tenant (set deleted_at)
    async with engine.connect() as conn:
        await conn.execute(
            text("UPDATE public.tenants SET deleted_at = now() WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        await conn.commit()

    # Try to accept invite as new user - should fail with tenant validation error
    async with AsyncSession(engine) as session:
        invite_repo = TenantInviteRepository(session)
        user_repo = UserRepository(session)
        membership_repo = MembershipRepository(session)
        tenant_repo = TenantRepository(session)

        invite_service = InviteService(
            invite_repo=invite_repo,
            user_repo=user_repo,
            membership_repo=membership_repo,
            tenant_repo=tenant_repo,
            session=session,
        )

        with pytest.raises(ValueError, match="Tenant is no longer available"):
            await invite_service.accept_invite_new_user(
                token=token,
                email=invite_email,
                password="newpassword123",
                full_name="New User",
            )

    # Verify no user was created despite the error
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM public.users WHERE email = :email"),
            {"email": invite_email},
        )
        user_count = result.scalar_one()
        assert user_count == 0, "No user should be created when tenant is deleted"

        # Un-delete tenant for cleanup
        await conn.execute(
            text("UPDATE public.tenants SET deleted_at = NULL WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_accept_invite_nonexistent_tenant_existing_user(
    engine: AsyncEngine,
    test_tenant: str,
):
    """Test that accepting an invite for a non-existent tenant fails (existing user flow).

    This simulates the edge case where tenant is hard-deleted (not just soft-deleted).
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.app.models.public import User
    from src.app.repositories import (
        MembershipRepository,
        TenantInviteRepository,
        TenantRepository,
        UserRepository,
    )
    from src.app.services.invite_service import InviteService

    invite_email = f"invite_{uuid7().hex[-8:]}@example.com"
    token = secrets.token_urlsafe(32)
    token_hash = sha256(token.encode()).hexdigest()

    # Create invite pointing to a fake tenant ID
    fake_tenant_id = uuid7()
    user_id = uuid7()

    async with engine.connect() as conn:
        # Create invite with non-existent tenant
        await conn.execute(
            text(
                """
                INSERT INTO public.tenant_invites
                (id, tenant_id, email, token_hash, role, status,
                 invited_by_user_id, expires_at, created_at)
                VALUES (gen_random_uuid(), :tenant_id, :email, :token_hash,
                 'member', 'pending', NULL, now() + interval '7 days', now())
                """
            ),
            {
                "tenant_id": fake_tenant_id,
                "email": invite_email,
                "token_hash": token_hash,
            },
        )

        # Create user
        await conn.execute(
            text(
                """
                INSERT INTO public.users
                (id, email, hashed_password, full_name, is_active, is_superuser,
                 email_verified, email_verified_at, created_at, updated_at)
                VALUES (:id, :email, :hashed_password, :full_name, true, false,
                 true, now(), now(), now())
                """
            ),
            {
                "id": user_id,
                "email": invite_email,
                "hashed_password": hash_password("password123"),
                "full_name": "Test User",
            },
        )
        await conn.commit()

    # Try to accept invite - should fail with tenant validation error
    async with AsyncSession(engine) as session:
        user = await session.get(User, user_id)

        invite_repo = TenantInviteRepository(session)
        user_repo = UserRepository(session)
        membership_repo = MembershipRepository(session)
        tenant_repo = TenantRepository(session)

        invite_service = InviteService(
            invite_repo=invite_repo,
            user_repo=user_repo,
            membership_repo=membership_repo,
            tenant_repo=tenant_repo,
            session=session,
        )

        with pytest.raises(ValueError, match="Tenant is no longer available"):
            await invite_service.accept_invite_existing_user(token, user)

    # Cleanup
    async with engine.connect() as conn:
        await conn.execute(
            text("DELETE FROM public.tenant_invites WHERE email = :email"),
            {"email": invite_email},
        )
        await conn.execute(
            text("DELETE FROM public.users WHERE id = :id"),
            {"id": user_id},
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_accept_invite_success_returns_tenant_existing_user(
    engine: AsyncEngine,
    test_tenant: str,
    invite_token_and_tenant: tuple[str, str, str],
):
    """Test that accepting invite successfully returns tenant object (existing user).

    This validates that the tenant is retrieved within the transaction and
    returned to the caller, eliminating the need for a separate query.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.app.models.public import Tenant, User
    from src.app.repositories import (
        MembershipRepository,
        TenantInviteRepository,
        TenantRepository,
        UserRepository,
    )
    from src.app.services.invite_service import InviteService

    token, invite_email, tenant_id = invite_token_and_tenant

    # Create user
    user_id = uuid7()
    async with engine.connect() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO public.users
                (id, email, hashed_password, full_name, is_active, is_superuser,
                 email_verified, email_verified_at, created_at, updated_at)
                VALUES (:id, :email, :hashed_password, :full_name, true, false,
                 true, now(), now(), now())
                """
            ),
            {
                "id": user_id,
                "email": invite_email,
                "hashed_password": hash_password("password123"),
                "full_name": "Test User",
            },
        )
        await conn.commit()

    # Accept invite
    async with AsyncSession(engine) as session:
        user = await session.get(User, user_id)

        invite_repo = TenantInviteRepository(session)
        user_repo = UserRepository(session)
        membership_repo = MembershipRepository(session)
        tenant_repo = TenantRepository(session)

        invite_service = InviteService(
            invite_repo=invite_repo,
            user_repo=user_repo,
            membership_repo=membership_repo,
            tenant_repo=tenant_repo,
            session=session,
        )

        invite, accepted_user, tenant = await invite_service.accept_invite_existing_user(
            token, user
        )

        # Validate returned values
        assert invite is not None
        assert accepted_user.id == user_id
        assert tenant is not None
        assert isinstance(tenant, Tenant)
        assert tenant.slug == test_tenant
        assert tenant.deleted_at is None
        assert str(tenant.id) == tenant_id

    # Cleanup
    async with engine.connect() as conn:
        await conn.execute(
            text("DELETE FROM public.user_tenant_membership WHERE user_id = :id"),
            {"id": user_id},
        )
        await conn.execute(
            text("DELETE FROM public.users WHERE id = :id"),
            {"id": user_id},
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_accept_invite_success_returns_tenant_new_user(
    engine: AsyncEngine,
    test_tenant: str,
    invite_token_and_tenant: tuple[str, str, str],
):
    """Test that accepting invite successfully returns tenant object (new user).

    This validates that the tenant is retrieved within the transaction and
    returned to the caller, eliminating the need for a separate query.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.app.models.public import Tenant
    from src.app.repositories import (
        MembershipRepository,
        TenantInviteRepository,
        TenantRepository,
        UserRepository,
    )
    from src.app.services.invite_service import InviteService

    token, invite_email, tenant_id = invite_token_and_tenant

    # Accept invite as new user
    async with AsyncSession(engine) as session:
        invite_repo = TenantInviteRepository(session)
        user_repo = UserRepository(session)
        membership_repo = MembershipRepository(session)
        tenant_repo = TenantRepository(session)

        invite_service = InviteService(
            invite_repo=invite_repo,
            user_repo=user_repo,
            membership_repo=membership_repo,
            tenant_repo=tenant_repo,
            session=session,
        )

        invite, new_user, tenant = await invite_service.accept_invite_new_user(
            token=token,
            email=invite_email,
            password="newpassword123",
            full_name="New User",
        )

        # Validate returned values
        assert invite is not None
        assert new_user is not None
        assert new_user.email == invite_email
        assert tenant is not None
        assert isinstance(tenant, Tenant)
        assert tenant.slug == test_tenant
        assert tenant.deleted_at is None
        assert str(tenant.id) == tenant_id

        created_user_id = new_user.id

    # Cleanup
    async with engine.connect() as conn:
        await conn.execute(
            text("DELETE FROM public.user_tenant_membership WHERE user_id = :id"),
            {"id": created_user_id},
        )
        await conn.execute(
            text("DELETE FROM public.users WHERE id = :id"),
            {"id": created_user_id},
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_api_accept_invite_deleted_tenant_existing_user(
    engine: AsyncEngine,
    test_tenant: str,
    client_no_tenant,
    invite_token_and_tenant: tuple[str, str, str],
):
    """Test API endpoint rejects accept for deleted tenant (existing user).

    This validates the end-to-end flow through the API endpoint.
    """

    token, invite_email, tenant_id = invite_token_and_tenant

    # Create and login user
    user_id = uuid7()
    async with engine.connect() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO public.users
                (id, email, hashed_password, full_name, is_active, is_superuser,
                 email_verified, email_verified_at, created_at, updated_at)
                VALUES (:id, :email, :hashed_password, :full_name, true, false,
                 true, now(), now(), now())
                """
            ),
            {
                "id": user_id,
                "email": invite_email,
                "hashed_password": hash_password("password123"),
                "full_name": "Test User",
            },
        )
        await conn.commit()

    # Login to get auth token
    login_response = await client_no_tenant.post(
        "/api/v1/auth/login",
        json={"email": invite_email, "password": "password123"},
    )
    assert login_response.status_code == 200
    auth_token = login_response.json()["access_token"]

    # Soft-delete the tenant
    async with engine.connect() as conn:
        await conn.execute(
            text("UPDATE public.tenants SET deleted_at = now() WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        await conn.commit()

    # Try to accept invite via API - should fail
    response = await client_no_tenant.post(
        f"/api/v1/invites/t/{token}/accept",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 400
    assert "Tenant is no longer available" in response.json()["detail"]

    # Verify no membership was created
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM public.user_tenant_membership WHERE user_id = :id"),
            {"id": user_id},
        )
        membership_count = result.scalar_one()
        assert membership_count == 0, "No membership should be created for deleted tenant"

        # Cleanup
        await conn.execute(
            text("DELETE FROM public.users WHERE id = :id"),
            {"id": user_id},
        )
        await conn.execute(
            text("UPDATE public.tenants SET deleted_at = NULL WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_api_accept_invite_deleted_tenant_new_user(
    engine: AsyncEngine,
    test_tenant: str,
    client_no_tenant,
    invite_token_and_tenant: tuple[str, str, str],
):
    """Test API endpoint rejects accept for deleted tenant (new user).

    This validates the end-to-end flow through the API endpoint.
    """
    token, invite_email, tenant_id = invite_token_and_tenant

    # Soft-delete the tenant
    async with engine.connect() as conn:
        await conn.execute(
            text("UPDATE public.tenants SET deleted_at = now() WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        await conn.commit()

    # Try to accept invite as new user via API - should fail
    response = await client_no_tenant.post(
        f"/api/v1/invites/t/{token}/accept",
        json={
            "type": "new",
            "email": invite_email,
            "password": "newpassword123",
            "full_name": "New User",
        },
    )

    assert response.status_code == 400
    assert "Tenant is no longer available" in response.json()["detail"]

    # Verify no user was created
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM public.users WHERE email = :email"),
            {"email": invite_email},
        )
        user_count = result.scalar_one()
        assert user_count == 0, "No user should be created for deleted tenant"

        # Cleanup
        await conn.execute(
            text("UPDATE public.tenants SET deleted_at = NULL WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        await conn.commit()
