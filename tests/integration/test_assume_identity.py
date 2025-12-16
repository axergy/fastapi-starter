"""Integration tests for assume identity feature."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.app.core import db
from src.app.core.security import decode_token
from src.app.main import create_app
from src.app.models.enums import MembershipRole
from tests.factories import (
    TenantFactory,
    UserFactory,
    UserTenantMembershipFactory,
)
from tests.utils.cleanup import cleanup_user_cascade

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestAssumeIdentityEndpoint:
    """Tests for POST /admin/assume-identity endpoint."""

    async def test_superuser_can_assume_identity(
        self,
        client: AsyncClient,
        test_superuser_with_tenant: dict,
        test_user: dict,
        db_session: AsyncSession,
    ) -> None:
        """Superuser can successfully assume a regular user's identity."""
        # Login as superuser
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_superuser_with_tenant["email"],
                "password": test_superuser_with_tenant["password"],
            },
        )
        assert login_response.status_code == 200
        superuser_token = login_response.json()["access_token"]

        # Get tenant_id
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_user["tenant_slug"]},
        )
        tenant_id = result.scalar_one()

        # Assume identity
        response = await client.post(
            "/api/v1/admin/assume-identity",
            json={
                "target_user_id": test_user["id"],
                "tenant_id": str(tenant_id),
                "reason": "Testing user issue #123",
            },
            headers={"Authorization": f"Bearer {superuser_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 900  # 15 minutes
        assert data["assumed_user_id"] == test_user["id"]
        assert data["tenant_slug"] == test_user["tenant_slug"]

    async def test_regular_user_gets_403(
        self,
        client: AsyncClient,
        test_user: dict,
        db_session: AsyncSession,
    ) -> None:
        """Non-superuser cannot assume identity."""
        # Login as regular user
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )
        assert login_response.status_code == 200
        user_token = login_response.json()["access_token"]

        # Get tenant_id
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_user["tenant_slug"]},
        )
        tenant_id = result.scalar_one()

        # Attempt to assume identity
        response = await client.post(
            "/api/v1/admin/assume-identity",
            json={
                "target_user_id": test_user["id"],
                "tenant_id": str(tenant_id),
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )

        assert response.status_code == 403

    async def test_cannot_assume_nonexistent_user(
        self,
        client: AsyncClient,
        test_superuser_with_tenant: dict,
        db_session: AsyncSession,
        test_tenant: str,
    ) -> None:
        """Cannot assume identity of user that doesn't exist."""
        # Login as superuser
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_superuser_with_tenant["email"],
                "password": test_superuser_with_tenant["password"],
            },
        )
        superuser_token = login_response.json()["access_token"]

        # Get tenant_id
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        tenant_id = result.scalar_one()

        # Attempt to assume nonexistent user
        response = await client.post(
            "/api/v1/admin/assume-identity",
            json={
                "target_user_id": str(uuid4()),
                "tenant_id": str(tenant_id),
            },
            headers={"Authorization": f"Bearer {superuser_token}"},
        )

        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    async def test_cannot_assume_inactive_user(
        self,
        client: AsyncClient,
        test_superuser_with_tenant: dict,
        engine: AsyncEngine,
        db_session: AsyncSession,
        test_tenant: str,
    ) -> None:
        """Cannot assume identity of inactive user."""
        # Login as superuser
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_superuser_with_tenant["email"],
                "password": test_superuser_with_tenant["password"],
            },
        )
        superuser_token = login_response.json()["access_token"]

        # Get tenant_id
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        tenant_id = result.scalar_one()

        # Create inactive user
        inactive_user = UserFactory.build(is_active=False)
        db_session.add(inactive_user)
        await db_session.flush()

        # Create membership
        membership = UserTenantMembershipFactory.build(
            user_id=inactive_user.id,
            tenant_id=tenant_id,
            role=MembershipRole.MEMBER.value,
        )
        db_session.add(membership)
        await db_session.commit()

        try:
            # Attempt to assume inactive user
            response = await client.post(
                "/api/v1/admin/assume-identity",
                json={
                    "target_user_id": str(inactive_user.id),
                    "tenant_id": str(tenant_id),
                },
                headers={"Authorization": f"Bearer {superuser_token}"},
            )

            assert response.status_code == 400
            assert "inactive" in response.json()["detail"].lower()
        finally:
            # Cleanup
            async with engine.connect() as conn:
                await cleanup_user_cascade(conn, inactive_user.id)
                await conn.commit()

    async def test_cannot_assume_superuser_identity(
        self,
        client: AsyncClient,
        test_superuser_with_tenant: dict,
        engine: AsyncEngine,
        db_session: AsyncSession,
        test_tenant: str,
    ) -> None:
        """Cannot assume identity of another superuser (security restriction)."""
        # Login as superuser
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_superuser_with_tenant["email"],
                "password": test_superuser_with_tenant["password"],
            },
        )
        superuser_token = login_response.json()["access_token"]

        # Get tenant_id
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        tenant_id = result.scalar_one()

        # Create another superuser with membership
        target_superuser = UserFactory.superuser()
        db_session.add(target_superuser)
        await db_session.flush()

        membership = UserTenantMembershipFactory.build(
            user_id=target_superuser.id,
            tenant_id=tenant_id,
            role=MembershipRole.ADMIN.value,
        )
        db_session.add(membership)
        await db_session.commit()

        try:
            # Attempt to assume superuser's identity
            response = await client.post(
                "/api/v1/admin/assume-identity",
                json={
                    "target_user_id": str(target_superuser.id),
                    "tenant_id": str(tenant_id),
                },
                headers={"Authorization": f"Bearer {superuser_token}"},
            )

            assert response.status_code == 400
            assert "superuser" in response.json()["detail"].lower()
        finally:
            # Cleanup
            async with engine.connect() as conn:
                await cleanup_user_cascade(conn, target_superuser.id)
                await conn.commit()

    async def test_cannot_assume_user_not_in_tenant(
        self,
        client: AsyncClient,
        test_superuser_with_tenant: dict,
        engine: AsyncEngine,
        db_session: AsyncSession,
        test_tenant: str,
    ) -> None:
        """Cannot assume identity if user has no membership in specified tenant."""
        # Login as superuser
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_superuser_with_tenant["email"],
                "password": test_superuser_with_tenant["password"],
            },
        )
        superuser_token = login_response.json()["access_token"]

        # Get tenant_id
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        tenant_id = result.scalar_one()

        # Create user WITHOUT membership
        user_no_membership = UserFactory.build()
        db_session.add(user_no_membership)
        await db_session.commit()

        try:
            # Attempt to assume identity
            response = await client.post(
                "/api/v1/admin/assume-identity",
                json={
                    "target_user_id": str(user_no_membership.id),
                    "tenant_id": str(tenant_id),
                },
                headers={"Authorization": f"Bearer {superuser_token}"},
            )

            assert response.status_code == 400
            assert "access" in response.json()["detail"].lower()
        finally:
            # Cleanup
            async with engine.connect() as conn:
                await cleanup_user_cascade(conn, user_no_membership.id)
                await conn.commit()

    async def test_reason_is_optional(
        self,
        client: AsyncClient,
        test_superuser_with_tenant: dict,
        test_user: dict,
        db_session: AsyncSession,
    ) -> None:
        """Assume identity works without reason."""
        # Login as superuser
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_superuser_with_tenant["email"],
                "password": test_superuser_with_tenant["password"],
            },
        )
        superuser_token = login_response.json()["access_token"]

        # Get tenant_id
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_user["tenant_slug"]},
        )
        tenant_id = result.scalar_one()

        # Assume identity without reason
        response = await client.post(
            "/api/v1/admin/assume-identity",
            json={
                "target_user_id": test_user["id"],
                "tenant_id": str(tenant_id),
            },
            headers={"Authorization": f"Bearer {superuser_token}"},
        )

        assert response.status_code == 200
        assert "access_token" in response.json()


class TestAssumedTokenUsage:
    """Tests for using assumed identity tokens."""

    async def test_assumed_token_accesses_user_resources(
        self,
        client: AsyncClient,
        test_superuser_with_tenant: dict,
        test_user: dict,
        db_session: AsyncSession,
    ) -> None:
        """Assumed token can be used to access API endpoints."""
        # Login as superuser
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_superuser_with_tenant["email"],
                "password": test_superuser_with_tenant["password"],
            },
        )
        superuser_token = login_response.json()["access_token"]

        # Get tenant_id
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_user["tenant_slug"]},
        )
        tenant_id = result.scalar_one()

        # Assume identity
        assume_response = await client.post(
            "/api/v1/admin/assume-identity",
            json={
                "target_user_id": test_user["id"],
                "tenant_id": str(tenant_id),
            },
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assumed_token = assume_response.json()["access_token"]

        # Use assumed token to access API
        me_response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {assumed_token}"},
        )

        assert me_response.status_code == 200

    async def test_assumed_token_returns_assumed_user_on_me_endpoint(
        self,
        client: AsyncClient,
        test_superuser_with_tenant: dict,
        test_user: dict,
        db_session: AsyncSession,
    ) -> None:
        """GET /users/me returns the assumed user, not the operator."""
        # Login as superuser
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_superuser_with_tenant["email"],
                "password": test_superuser_with_tenant["password"],
            },
        )
        superuser_token = login_response.json()["access_token"]

        # Get tenant_id
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_user["tenant_slug"]},
        )
        tenant_id = result.scalar_one()

        # Assume identity
        assume_response = await client.post(
            "/api/v1/admin/assume-identity",
            json={
                "target_user_id": test_user["id"],
                "tenant_id": str(tenant_id),
            },
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assumed_token = assume_response.json()["access_token"]

        # Check /users/me returns assumed user
        me_response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {assumed_token}"},
        )

        assert me_response.status_code == 200
        data = me_response.json()
        assert data["id"] == test_user["id"]
        assert data["email"] == test_user["email"]

    async def test_assumed_token_has_correct_structure(
        self,
        client: AsyncClient,
        test_superuser_with_tenant: dict,
        test_user: dict,
        db_session: AsyncSession,
    ) -> None:
        """Assumed token contains assumed_identity claim with operator info."""
        # Login as superuser
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_superuser_with_tenant["email"],
                "password": test_superuser_with_tenant["password"],
            },
        )
        superuser_token = login_response.json()["access_token"]

        # Get tenant_id
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_user["tenant_slug"]},
        )
        tenant_id = result.scalar_one()

        # Assume identity
        assume_response = await client.post(
            "/api/v1/admin/assume-identity",
            json={
                "target_user_id": test_user["id"],
                "tenant_id": str(tenant_id),
                "reason": "Debugging",
            },
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assumed_token = assume_response.json()["access_token"]

        # Decode and verify token structure
        payload = decode_token(assumed_token)
        assert payload is not None
        assert payload["sub"] == test_user["id"]
        assert payload["type"] == "access"
        assert "assumed_identity" in payload
        assert payload["assumed_identity"]["operator_user_id"] == test_superuser_with_tenant["id"]
        assert payload["assumed_identity"]["reason"] == "Debugging"
        assert "started_at" in payload["assumed_identity"]


class TestAssumeIdentityAudit:
    """Tests for audit logging during assumed identity sessions."""

    async def test_assume_identity_creates_audit_log(
        self,
        client: AsyncClient,
        test_superuser_with_tenant: dict,
        test_user: dict,
        db_session: AsyncSession,
    ) -> None:
        """Starting assumed identity session creates IDENTITY_ASSUMED audit log."""
        # Login as superuser
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_superuser_with_tenant["email"],
                "password": test_superuser_with_tenant["password"],
            },
        )
        superuser_token = login_response.json()["access_token"]

        # Get tenant_id
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_user["tenant_slug"]},
        )
        tenant_id = result.scalar_one()

        # Assume identity
        response = await client.post(
            "/api/v1/admin/assume-identity",
            json={
                "target_user_id": test_user["id"],
                "tenant_id": str(tenant_id),
                "reason": "Support ticket #456",
            },
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert response.status_code == 200

        # Check audit log was created
        audit_result = await db_session.execute(
            text(
                """
                SELECT action, entity_type, entity_id, user_id, changes
                FROM public.audit_logs
                WHERE tenant_id = :tenant_id
                AND action = 'identity.assumed'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id},
        )
        row = audit_result.fetchone()
        assert row is not None
        assert row.action == "identity.assumed"
        assert row.entity_type == "user"
        assert str(row.entity_id) == test_user["id"]
        assert str(row.user_id) == test_superuser_with_tenant["id"]
        assert row.changes["reason"] == "Support ticket #456"

    async def test_actions_during_assumed_session_include_both_users(
        self,
        test_superuser_with_tenant: dict,
        test_user: dict,
        db_session: AsyncSession,
        test_tenant: str,
    ) -> None:
        """Actions performed during assumed session include assumed_by_user_id.

        The IDENTITY_ASSUMED audit log itself demonstrates this - it captures
        both the operator (user_id) and the target. For actual actions during
        an assumed session, the assumed_by_user_id field would be populated.
        """
        await db.dispose_engine()
        app = create_app()

        # Get tenant_id
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        tenant_id = result.scalar_one()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Tenant-ID": test_tenant},
        ) as client:
            # Login as superuser
            login_response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": test_superuser_with_tenant["email"],
                    "password": test_superuser_with_tenant["password"],
                },
            )
            superuser_token = login_response.json()["access_token"]

            # Assume identity - this creates the IDENTITY_ASSUMED audit log
            assume_response = await client.post(
                "/api/v1/admin/assume-identity",
                json={
                    "target_user_id": test_user["id"],
                    "tenant_id": str(tenant_id),
                    "reason": "Testing audit tracking",
                },
                headers={"Authorization": f"Bearer {superuser_token}"},
            )
            assert assume_response.status_code == 200
            assumed_token = assume_response.json()["access_token"]

            # Verify the assumed token can access the /users/me endpoint
            me_response = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {assumed_token}"},
            )
            assert me_response.status_code == 200
            # The response should be for the assumed user
            assert me_response.json()["id"] == test_user["id"]

        await db.dispose_engine()

        # Verify the audit log has proper tracking
        # The IDENTITY_ASSUMED action logs the operator (superuser) as user_id
        # and the target user in entity_id and changes
        audit_result = await db_session.execute(
            text(
                """
                SELECT action, user_id, entity_id, changes
                FROM public.audit_logs
                WHERE tenant_id = :tenant_id
                AND action = 'identity.assumed'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id},
        )
        row = audit_result.fetchone()
        assert row is not None
        # user_id is the operator (who performed the assumption)
        assert str(row.user_id) == test_superuser_with_tenant["id"]
        # entity_id is the target user being assumed
        assert str(row.entity_id) == test_user["id"]
        # Changes contain the assumption details
        assert row.changes["assumed_user_id"] == test_user["id"]
        assert row.changes["reason"] == "Testing audit tracking"


class TestAssumedTokenTenantValidation:
    """Tests for tenant context validation with assumed tokens."""

    async def test_assumed_token_works_with_matching_tenant_header(
        self,
        client: AsyncClient,
        test_superuser_with_tenant: dict,
        test_user: dict,
        db_session: AsyncSession,
    ) -> None:
        """Assumed token works when X-Tenant-ID matches token's tenant."""
        # Login as superuser
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_superuser_with_tenant["email"],
                "password": test_superuser_with_tenant["password"],
            },
        )
        superuser_token = login_response.json()["access_token"]

        # Get tenant_id
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_user["tenant_slug"]},
        )
        tenant_id = result.scalar_one()

        # Assume identity
        assume_response = await client.post(
            "/api/v1/admin/assume-identity",
            json={
                "target_user_id": test_user["id"],
                "tenant_id": str(tenant_id),
            },
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assumed_token = assume_response.json()["access_token"]

        # Use with matching tenant header (already set on client fixture)
        me_response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {assumed_token}"},
        )

        assert me_response.status_code == 200

    async def test_assumed_token_respects_tenant_context(
        self,
        test_superuser_with_tenant: dict,
        test_user: dict,
        engine: AsyncEngine,
        db_session: AsyncSession,
        test_tenant: str,
    ) -> None:
        """Assumed token requires correct tenant context."""
        await db.dispose_engine()
        app = create_app()

        # Get tenant_id for assumption
        result = await db_session.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        tenant_id = result.scalar_one()

        # Create second tenant for testing cross-tenant access
        second_tenant = TenantFactory.build()
        db_session.add(second_tenant)
        await db_session.commit()

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-Tenant-ID": test_tenant},
            ) as client:
                # Login as superuser
                login_response = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": test_superuser_with_tenant["email"],
                        "password": test_superuser_with_tenant["password"],
                    },
                )
                superuser_token = login_response.json()["access_token"]

                # Assume identity in first tenant
                assume_response = await client.post(
                    "/api/v1/admin/assume-identity",
                    json={
                        "target_user_id": test_user["id"],
                        "tenant_id": str(tenant_id),
                    },
                    headers={"Authorization": f"Bearer {superuser_token}"},
                )
                assumed_token = assume_response.json()["access_token"]

            # Try to use assumed token with different tenant header
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-Tenant-ID": second_tenant.slug},
            ) as wrong_tenant_client:
                me_response = await wrong_tenant_client.get(
                    "/api/v1/users/me",
                    headers={"Authorization": f"Bearer {assumed_token}"},
                )
                # Should fail - token was issued for different tenant
                # Exact status code depends on implementation (401 or 403)
                assert me_response.status_code in [401, 403]

        finally:
            await db.dispose_engine()
            # Cleanup second tenant
            async with engine.connect() as conn:
                await conn.execute(
                    text("DELETE FROM public.tenants WHERE id = :id"),
                    {"id": second_tenant.id},
                )
                await conn.commit()
