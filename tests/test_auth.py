"""Tests for authentication endpoints - Lobby Pattern."""

from unittest.mock import AsyncMock, patch
from uuid import uuid7

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestRegistration:
    """Tests for user + tenant registration (Lobby Pattern)."""

    async def test_register_creates_user_and_tenant(self, client_no_tenant: AsyncClient) -> None:
        """Test registration creates user and starts tenant provisioning workflow."""
        # Use unique values per test run to avoid parallel test interference
        unique_id = uuid7().hex[-8:]
        test_email = f"newuser_{unique_id}@example.com"
        test_slug = f"new_company_{unique_id}"

        with patch("src.app.services.registration_service.get_temporal_client") as mock_get_client:
            # Mock Temporal client
            mock_client = AsyncMock()
            mock_client.start_workflow.return_value = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await client_no_tenant.post(
                "/api/v1/auth/register",
                json={
                    "email": test_email,
                    "password": "correct-horse-battery-staple",
                    "full_name": "New User",
                    "tenant_name": "New Company",
                    "tenant_slug": test_slug,
                },
            )

        assert response.status_code == 202
        data = response.json()
        assert data["user"]["email"] == test_email
        assert data["user"]["full_name"] == "New User"
        assert data["tenant_slug"] == test_slug
        assert "workflow_id" in data

    async def test_register_duplicate_email_fails(self, client_no_tenant: AsyncClient) -> None:
        """Test registration fails for duplicate email."""
        # Use unique email/slugs per test run to avoid parallel test interference
        unique_id = uuid7().hex[-8:]
        test_email = f"duplicate_{unique_id}@example.com"
        slug_one = f"company_one_{unique_id}"
        slug_two = f"company_two_{unique_id}"

        with patch("src.app.services.registration_service.get_temporal_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.start_workflow.return_value = AsyncMock()
            mock_get_client.return_value = mock_client

            # First registration
            first_response = await client_no_tenant.post(
                "/api/v1/auth/register",
                json={
                    "email": test_email,
                    "password": "correct-horse-battery-staple",
                    "full_name": "First User",
                    "tenant_name": "Company One",
                    "tenant_slug": slug_one,
                },
            )
            assert (
                first_response.status_code == 202
            ), f"First registration failed: {first_response.json()}"

            # Second registration with same email - must happen immediately
            # (no other operations in between that could allow cleanup to run)
            response = await client_no_tenant.post(
                "/api/v1/auth/register",
                json={
                    "email": test_email,
                    "password": "purple-monkey-dishwasher-99",
                    "full_name": "Second User",
                    "tenant_name": "Company Two",
                    "tenant_slug": slug_two,
                },
            )

            # Expect 409 Conflict for duplicate email
            assert (
                response.status_code == 409
            ), f"Expected 409 for duplicate email, got {response.status_code}: {response.json()}"

    async def test_register_invalid_slug_format(self, client_no_tenant: AsyncClient) -> None:
        """Test registration fails for invalid tenant slug format."""
        response = await client_no_tenant.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "correct-horse-battery-staple",
                "full_name": "Test User",
                "tenant_name": "Test Company",
                "tenant_slug": "Invalid-Slug!",  # Invalid: uppercase, hyphen, special char
            },
        )

        assert response.status_code == 422  # Validation error


class TestLogin:
    """Tests for login with tenant membership validation."""

    async def test_login_with_membership(self, client: AsyncClient, test_user: dict) -> None:
        """Test successful login when user has membership in tenant."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials(self, client: AsyncClient) -> None:
        """Test login with invalid credentials fails."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401

    async def test_login_requires_tenant_header(
        self, client_no_tenant: AsyncClient, test_user: dict
    ) -> None:
        """Test login fails without X-Tenant-ID header."""
        response = await client_no_tenant.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )

        assert response.status_code == 400
        assert "X-Tenant-ID" in response.json()["detail"]


class TestTokenOperations:
    """Tests for token refresh and logout."""

    async def test_refresh_token(self, client: AsyncClient, test_user: dict) -> None:
        """Test refreshing access token."""
        # Login first
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_invalid_token(self, client: AsyncClient) -> None:
        """Test refresh with invalid token fails."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )

        assert response.status_code == 401

    async def test_logout_revokes_token(self, client: AsyncClient, test_user: dict) -> None:
        """Test logout revokes refresh token."""
        # Login
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["password"],
            },
        )
        refresh_token = login_response.json()["refresh_token"]

        # Logout
        logout_response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert logout_response.status_code == 204

        # Try to refresh with revoked token
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 401


class TestCurrentUser:
    """Tests for authenticated user endpoints."""

    async def test_get_current_user(self, client: AsyncClient, test_user: dict) -> None:
        """Test getting current user with valid token."""
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
        assert data["email"] == test_user["email"]

    async def test_get_current_user_invalid_token(self, client: AsyncClient) -> None:
        """Test getting current user with invalid token fails."""
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401

    async def test_get_current_user_no_auth_header(self, client: AsyncClient) -> None:
        """Test getting current user without auth header fails."""
        response = await client.get("/api/v1/users/me")

        assert response.status_code == 401
