"""Tests for admin endpoints (superuser only)."""

from unittest.mock import AsyncMock, patch
from uuid import uuid7

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.app.core import db
from src.app.core.security import create_access_token
from src.app.main import create_app
from tests.factories import TenantFactory

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestListAllTenants:
    """Tests for GET /api/v1/admin/tenants endpoint."""

    async def test_list_tenants_as_superuser(
        self, engine: AsyncEngine, test_superuser: dict, test_tenant: str
    ) -> None:
        """Test superuser can list all tenants."""
        # Verify superuser exists in DB before testing
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT id, is_superuser FROM public.users WHERE id = :id"),
                {"id": test_superuser["id"]},
            )
            user_row = result.fetchone()
            assert user_row is not None, "Superuser not found in database"
            assert user_row[1] is True, "User is not a superuser"

        # Create access token for superuser (no tenant_id needed for superuser)
        access_token = create_access_token(
            subject=test_superuser["id"],
            tenant_id="00000000-0000-0000-0000-000000000000",  # dummy tenant for token
        )

        await db.dispose_engine()
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/admin/tenants",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.json()}"
        data = response.json()
        # Response is now paginated
        assert isinstance(data, dict)
        assert "items" in data
        assert "next_cursor" in data
        assert "has_more" in data
        items = data["items"]
        # At least the test tenant should exist
        assert len(items) >= 1
        # Verify tenant data structure
        assert all("id" in t for t in items)
        assert all("slug" in t for t in items)
        assert all("name" in t for t in items)
        assert all("status" in t for t in items)

    async def test_list_tenants_as_regular_user_forbidden(
        self, client: AsyncClient, test_user: dict
    ) -> None:
        """Test regular user cannot access admin endpoints."""
        # Login as regular user
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )
        access_token = login_response.json()["access_token"]

        # Try to access admin endpoint
        response = await client.get(
            "/api/v1/admin/tenants",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 403
        assert "Superuser privileges required" in response.json()["detail"]

    async def test_list_tenants_no_auth_unauthorized(
        self, engine: AsyncEngine, test_tenant: str
    ) -> None:
        """Test unauthenticated request returns 401."""
        await db.dispose_engine()
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/admin/tenants")

        assert response.status_code == 401

    async def test_list_tenants_invalid_token_unauthorized(
        self, engine: AsyncEngine, test_tenant: str
    ) -> None:
        """Test invalid token returns 401."""
        await db.dispose_engine()
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/admin/tenants",
                headers={"Authorization": "Bearer invalid-token"},
            )

        assert response.status_code == 401


class TestUserReadSchema:
    """Tests for is_superuser field in UserRead schema."""

    async def test_user_response_includes_is_superuser_false(
        self, client: AsyncClient, test_user: dict
    ) -> None:
        """Test regular user response includes is_superuser=false."""
        # Login
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )
        access_token = login_response.json()["access_token"]

        # Get current user
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "is_superuser" in data
        assert data["is_superuser"] is False

    async def test_superuser_response_includes_is_superuser_true(
        self, test_superuser_with_tenant: dict
    ) -> None:
        """Test superuser response includes is_superuser=true."""
        await db.dispose_engine()
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Tenant-Slug": test_superuser_with_tenant["tenant_slug"]},
        ) as client:
            # Login as superuser
            login_response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": test_superuser_with_tenant["email"],
                    "password": test_superuser_with_tenant["password"],
                },
            )
            assert login_response.status_code == 200, f"Login failed: {login_response.json()}"
            access_token = login_response.json()["access_token"]

            # Get current user
            response = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "is_superuser" in data
        assert data["is_superuser"] is True


class TestDeleteTenant:
    """Tests for DELETE /api/v1/admin/tenants/{tenant_id} endpoint."""

    async def test_delete_tenant_as_superuser(
        self, engine: AsyncEngine, test_superuser: dict, test_tenant_obj
    ) -> None:
        """Test superuser can delete a tenant."""
        tenant_id = str(test_tenant_obj.id)

        # Create access token for superuser
        access_token = create_access_token(
            subject=test_superuser["id"],
            tenant_id="00000000-0000-0000-0000-000000000000",
        )

        await db.dispose_engine()
        app = create_app()

        # Mock Temporal client
        with patch("src.app.services.admin_service.get_temporal_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.start_workflow.return_value = AsyncMock()
            mock_get_client.return_value = mock_client

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.delete(
                    f"/api/v1/admin/tenants/{tenant_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )

        assert response.status_code == 200, f"Got {response.status_code}: {response.json()}"
        data = response.json()
        assert data["status"] == "deletion_started"
        assert "workflow_id" in data
        assert tenant_id in data["workflow_id"]

        # Verify workflow was started
        mock_client.start_workflow.assert_called_once()

    async def test_delete_tenant_not_found(
        self, engine: AsyncEngine, test_superuser: dict, test_tenant: str
    ) -> None:
        """Test 404 when tenant doesn't exist."""
        access_token = create_access_token(
            subject=test_superuser["id"],
            tenant_id="00000000-0000-0000-0000-000000000000",
        )

        non_existent_id = str(uuid7())

        await db.dispose_engine()
        app = create_app()

        with patch("src.app.services.admin_service.get_temporal_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.delete(
                    f"/api/v1/admin/tenants/{non_existent_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

        # Verify workflow was NOT started
        mock_client.start_workflow.assert_not_called()

    async def test_delete_tenant_already_deleted(
        self, engine: AsyncEngine, test_superuser: dict, test_tenant_obj
    ) -> None:
        """Test 404 when tenant already soft-deleted."""
        tenant_id = str(test_tenant_obj.id)

        # Soft-delete the tenant
        async with engine.connect() as conn:
            await conn.execute(
                text("UPDATE public.tenants SET deleted_at = now() WHERE id = :id"),
                {"id": test_tenant_obj.id},
            )
            await conn.commit()

        access_token = create_access_token(
            subject=test_superuser["id"],
            tenant_id="00000000-0000-0000-0000-000000000000",
        )

        await db.dispose_engine()
        app = create_app()

        with patch("src.app.services.admin_service.get_temporal_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.delete(
                    f"/api/v1/admin/tenants/{tenant_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )

        assert response.status_code == 404
        assert "already deleted" in response.json()["detail"].lower()

        # Verify workflow was NOT started
        mock_client.start_workflow.assert_not_called()

    async def test_delete_tenant_as_regular_user_forbidden(
        self, client: AsyncClient, test_user: dict
    ) -> None:
        """Test regular user cannot delete tenants."""
        # Login as regular user
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )
        access_token = login_response.json()["access_token"]

        fake_tenant_id = str(uuid7())

        response = await client.delete(
            f"/api/v1/admin/tenants/{fake_tenant_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 403
        assert "Superuser privileges required" in response.json()["detail"]

    async def test_delete_tenant_no_auth_unauthorized(
        self, engine: AsyncEngine, test_tenant_obj
    ) -> None:
        """Test unauthenticated request returns 401."""
        tenant_id = str(test_tenant_obj.id)

        await db.dispose_engine()
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete(f"/api/v1/admin/tenants/{tenant_id}")

        assert response.status_code == 401


class TestBulkDeleteTenants:
    """Tests for DELETE /api/v1/admin/tenants endpoint."""

    async def test_bulk_delete_by_status(
        self, engine: AsyncEngine, db_session: AsyncSession, test_superuser: dict, test_tenant: str
    ) -> None:
        """Test bulk delete with status filter."""
        # Create 2 failed tenants using factory
        failed_tenants = []
        for _ in range(2):
            tenant = TenantFactory.failed()
            db_session.add(tenant)
            failed_tenants.append(tenant)
        await db_session.commit()

        failed_slugs = [t.slug for t in failed_tenants]

        access_token = create_access_token(
            subject=test_superuser["id"],
            tenant_id="00000000-0000-0000-0000-000000000000",
        )

        await db.dispose_engine()
        app = create_app()

        try:
            with patch("src.app.services.admin_service.get_temporal_client") as mock_get_client:
                mock_client = AsyncMock()
                mock_client.start_workflow.return_value = AsyncMock()
                mock_get_client.return_value = mock_client

                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    response = await client.delete(
                        "/api/v1/admin/tenants?status=failed",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )

            assert response.status_code == 200, f"Got {response.status_code}: {response.json()}"
            data = response.json()
            assert data["status"] == "deletion_started"
            # At least the 2 tenants we created should be deleted
            # (may be more if other tests created failed tenants)
            assert data["count"] >= 2
            assert len(data["workflow_ids"]) >= 2

            # Verify workflow was started for at least our tenants
            assert mock_client.start_workflow.call_count >= 2
        finally:
            # Cleanup only the tenants we created (in case deletion didn't happen)
            async with engine.connect() as conn:
                for slug in failed_slugs:
                    await conn.execute(
                        text("DELETE FROM tenants WHERE slug = :slug"),
                        {"slug": slug},
                    )
                await conn.commit()

    async def test_bulk_delete_empty_result(
        self, engine: AsyncEngine, test_superuser: dict, test_tenant: str
    ) -> None:
        """Test bulk delete returns empty when no matching tenants."""
        access_token = create_access_token(
            subject=test_superuser["id"],
            tenant_id="00000000-0000-0000-0000-000000000000",
        )

        await db.dispose_engine()
        app = create_app()

        with patch("src.app.services.admin_service.get_temporal_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                # Use a status that doesn't exist
                response = await client.delete(
                    "/api/v1/admin/tenants?status=nonexistent_status",
                    headers={"Authorization": f"Bearer {access_token}"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deletion_started"
        assert data["count"] == 0
        assert data["workflow_ids"] == []

        # Verify no workflows were started
        mock_client.start_workflow.assert_not_called()

    async def test_bulk_delete_as_regular_user_forbidden(
        self, client: AsyncClient, test_user: dict
    ) -> None:
        """Test regular user cannot bulk delete."""
        # Login as regular user
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )
        access_token = login_response.json()["access_token"]

        response = await client.delete(
            "/api/v1/admin/tenants",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 403
        assert "Superuser privileges required" in response.json()["detail"]

    async def test_bulk_delete_no_auth_unauthorized(
        self, engine: AsyncEngine, test_tenant: str
    ) -> None:
        """Test unauthenticated bulk delete returns 401."""
        await db.dispose_engine()
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete("/api/v1/admin/tenants")

        assert response.status_code == 401


class TestTenantRepositoryDeletion:
    """Tests for TenantRepository.list_for_deletion method."""

    async def test_list_for_deletion_excludes_deleted(
        self, engine: AsyncEngine, test_tenant_obj
    ) -> None:
        """Test list_for_deletion excludes soft-deleted tenants."""
        from src.app.repositories import TenantRepository

        # Mark test_tenant as deleted
        async with engine.connect() as conn:
            await conn.execute(
                text("UPDATE public.tenants SET deleted_at = now() WHERE id = :id"),
                {"id": test_tenant_obj.id},
            )
            await conn.commit()

        # Create repository and test
        async with AsyncSession(engine) as session:
            repo = TenantRepository(session)
            tenants = await repo.list_for_deletion()

        # Assert test_tenant is NOT in results (since it's deleted)
        tenant_slugs = [t.slug for t in tenants]
        assert test_tenant_obj.slug not in tenant_slugs

    async def test_list_for_deletion_with_status_filter(
        self, engine: AsyncEngine, db_session: AsyncSession, test_tenant: str
    ) -> None:
        """Test list_for_deletion filters by status."""
        from src.app.repositories import TenantRepository

        # Create a failed tenant using factory
        failed_tenant = TenantFactory.failed()
        db_session.add(failed_tenant)
        await db_session.commit()

        try:
            # Test with status filter
            async with AsyncSession(engine) as session:
                repo = TenantRepository(session)
                tenants = await repo.list_for_deletion(status_filter="failed")

            tenant_slugs = [t.slug for t in tenants]
            # Our failed tenant should be in results
            assert failed_tenant.slug in tenant_slugs
            # test_tenant is 'ready', so should NOT be returned
            assert test_tenant not in tenant_slugs
        finally:
            # Cleanup the tenant we created
            async with engine.connect() as conn:
                await conn.execute(
                    text("DELETE FROM tenants WHERE slug = :slug"),
                    {"slug": failed_tenant.slug},
                )
                await conn.commit()

    async def test_list_for_deletion_no_filter(self, engine: AsyncEngine, test_tenant: str) -> None:
        """Test list_for_deletion without filter returns all non-deleted."""
        from src.app.repositories import TenantRepository

        async with AsyncSession(engine) as session:
            repo = TenantRepository(session)
            tenants = await repo.list_for_deletion()

        tenant_slugs = [t.slug for t in tenants]
        # test_tenant should be in results (not deleted)
        assert test_tenant in tenant_slugs
