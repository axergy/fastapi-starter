"""Tests for admin endpoints (superuser only)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.app.core import db
from src.app.core.security import create_access_token
from src.app.main import create_app

# Note: test_superuser_with_tenant fixture is defined in conftest.py

pytestmark = pytest.mark.asyncio


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
        assert isinstance(data, list)
        # At least the test tenant should exist
        assert len(data) >= 1
        # Verify tenant data structure
        assert all("id" in t for t in data)
        assert all("slug" in t for t in data)
        assert all("name" in t for t in data)
        assert all("status" in t for t in data)

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
            headers={"X-Tenant-ID": test_superuser_with_tenant["tenant_slug"]},
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
