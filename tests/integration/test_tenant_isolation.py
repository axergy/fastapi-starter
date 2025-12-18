"""Tests for tenant data isolation.

Verifies that tenant A cannot see tenant B's data, proving schema isolation.
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.app.core import db
from src.app.core.db import run_migrations_sync
from src.app.main import create_app
from src.app.models.enums import MembershipRole
from tests.factories import (
    DEFAULT_TEST_PASSWORD,
    TenantFactory,
    UserFactory,
    UserTenantMembershipFactory,
)
from tests.utils.cleanup import cleanup_tenant_cascade, cleanup_user_cascade, drop_tenant_schema

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
async def two_tenants(engine: AsyncEngine, db_session: AsyncSession):
    """Create two isolated tenants with their own schemas."""
    # Create tenant A
    tenant_a = TenantFactory.build(slug="tenant_a_isolation")
    db_session.add(tenant_a)
    await db_session.commit()
    await db_session.refresh(tenant_a)
    await asyncio.to_thread(run_migrations_sync, tenant_a.schema_name)

    # Create tenant B
    tenant_b = TenantFactory.build(slug="tenant_b_isolation")
    db_session.add(tenant_b)
    await db_session.commit()
    await db_session.refresh(tenant_b)
    await asyncio.to_thread(run_migrations_sync, tenant_b.schema_name)

    yield {"tenant_a": tenant_a, "tenant_b": tenant_b}

    # Cleanup
    async with engine.connect() as conn:
        await drop_tenant_schema(conn, tenant_a.schema_name)
        await cleanup_tenant_cascade(conn, tenant_a.id)
        await drop_tenant_schema(conn, tenant_b.schema_name)
        await cleanup_tenant_cascade(conn, tenant_b.id)
        await conn.commit()


@pytest.fixture
async def users_in_tenants(engine: AsyncEngine, db_session: AsyncSession, two_tenants):
    """Create users with membership in each tenant."""
    tenant_a = two_tenants["tenant_a"]
    tenant_b = two_tenants["tenant_b"]

    # User A in tenant A
    user_a = UserFactory.build()
    db_session.add(user_a)
    await db_session.flush()
    membership_a = UserTenantMembershipFactory.build(
        user_id=user_a.id,
        tenant_id=tenant_a.id,
        role=MembershipRole.ADMIN.value,
    )
    db_session.add(membership_a)

    # User B in tenant B
    user_b = UserFactory.build()
    db_session.add(user_b)
    await db_session.flush()
    membership_b = UserTenantMembershipFactory.build(
        user_id=user_b.id,
        tenant_id=tenant_b.id,
        role=MembershipRole.ADMIN.value,
    )
    db_session.add(membership_b)

    await db_session.commit()

    yield {
        "user_a": {
            "id": str(user_a.id),
            "email": user_a.email,
            "password": DEFAULT_TEST_PASSWORD,
        },
        "user_b": {
            "id": str(user_b.id),
            "email": user_b.email,
            "password": DEFAULT_TEST_PASSWORD,
        },
        "tenant_a_slug": tenant_a.slug,
        "tenant_b_slug": tenant_b.slug,
    }

    # Cleanup
    async with engine.connect() as conn:
        await cleanup_user_cascade(conn, user_a.id)
        await cleanup_user_cascade(conn, user_b.id)
        await conn.commit()


class TestTenantIsolation:
    """Tests verifying tenant data isolation via TenantDBSession."""

    async def test_tenant_a_cannot_see_tenant_b_projects(self, users_in_tenants):
        """Verify tenant A's projects are not visible to tenant B."""
        await db.dispose_engine()
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Login as user A (tenant A)
            login_a = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": users_in_tenants["user_a"]["email"],
                    "password": users_in_tenants["user_a"]["password"],
                },
                headers={"X-Tenant-Slug": users_in_tenants["tenant_a_slug"]},
            )
            assert login_a.status_code == 200
            token_a = login_a.json()["access_token"]

            # Create project in tenant A
            create_resp = await client.post(
                "/api/v1/projects",
                json={"name": "Secret Project A", "description": "Tenant A only"},
                headers={
                    "X-Tenant-Slug": users_in_tenants["tenant_a_slug"],
                    "Authorization": f"Bearer {token_a}",
                },
            )
            assert create_resp.status_code == 201
            project_a_id = create_resp.json()["id"]

            # Login as user B (tenant B)
            login_b = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": users_in_tenants["user_b"]["email"],
                    "password": users_in_tenants["user_b"]["password"],
                },
                headers={"X-Tenant-Slug": users_in_tenants["tenant_b_slug"]},
            )
            assert login_b.status_code == 200
            token_b = login_b.json()["access_token"]

            # Tenant B should see empty project list
            list_resp = await client.get(
                "/api/v1/projects",
                headers={
                    "X-Tenant-Slug": users_in_tenants["tenant_b_slug"],
                    "Authorization": f"Bearer {token_b}",
                },
            )
            assert list_resp.status_code == 200
            response_data = list_resp.json()
            assert response_data["items"] == []  # No projects visible
            assert response_data["has_more"] is False
            assert response_data["next_cursor"] is None

            # Tenant B should NOT be able to get tenant A's project by ID
            get_resp = await client.get(
                f"/api/v1/projects/{project_a_id}",
                headers={
                    "X-Tenant-Slug": users_in_tenants["tenant_b_slug"],
                    "Authorization": f"Bearer {token_b}",
                },
            )
            assert get_resp.status_code == 404  # Not found in tenant B's schema

        await db.dispose_engine()

    async def test_each_tenant_has_own_projects(self, users_in_tenants):
        """Verify each tenant maintains separate project lists."""
        await db.dispose_engine()
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Login as user A (tenant A)
            login_a = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": users_in_tenants["user_a"]["email"],
                    "password": users_in_tenants["user_a"]["password"],
                },
                headers={"X-Tenant-Slug": users_in_tenants["tenant_a_slug"]},
            )
            token_a = login_a.json()["access_token"]

            # Create project in tenant A
            await client.post(
                "/api/v1/projects",
                json={"name": "Project Alpha"},
                headers={
                    "X-Tenant-Slug": users_in_tenants["tenant_a_slug"],
                    "Authorization": f"Bearer {token_a}",
                },
            )

            # Login as user B (tenant B)
            login_b = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": users_in_tenants["user_b"]["email"],
                    "password": users_in_tenants["user_b"]["password"],
                },
                headers={"X-Tenant-Slug": users_in_tenants["tenant_b_slug"]},
            )
            token_b = login_b.json()["access_token"]

            # Create project in tenant B
            await client.post(
                "/api/v1/projects",
                json={"name": "Project Beta"},
                headers={
                    "X-Tenant-Slug": users_in_tenants["tenant_b_slug"],
                    "Authorization": f"Bearer {token_b}",
                },
            )

            # Verify tenant A sees only "Project Alpha"
            list_a = await client.get(
                "/api/v1/projects",
                headers={
                    "X-Tenant-Slug": users_in_tenants["tenant_a_slug"],
                    "Authorization": f"Bearer {token_a}",
                },
            )
            response_a = list_a.json()
            assert len(response_a["items"]) == 1
            assert response_a["items"][0]["name"] == "Project Alpha"

            # Verify tenant B sees only "Project Beta"
            list_b = await client.get(
                "/api/v1/projects",
                headers={
                    "X-Tenant-Slug": users_in_tenants["tenant_b_slug"],
                    "Authorization": f"Bearer {token_b}",
                },
            )
            response_b = list_b.json()
            assert len(response_b["items"]) == 1
            assert response_b["items"][0]["name"] == "Project Beta"

        await db.dispose_engine()

    async def test_project_crud_operations_isolated(self, users_in_tenants):
        """Verify CRUD operations are isolated per tenant."""
        await db.dispose_engine()
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Login as user A
            login_a = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": users_in_tenants["user_a"]["email"],
                    "password": users_in_tenants["user_a"]["password"],
                },
                headers={"X-Tenant-Slug": users_in_tenants["tenant_a_slug"]},
            )
            token_a = login_a.json()["access_token"]
            headers_a = {
                "X-Tenant-Slug": users_in_tenants["tenant_a_slug"],
                "Authorization": f"Bearer {token_a}",
            }

            # Create project
            create_resp = await client.post(
                "/api/v1/projects",
                json={"name": "Test Project", "description": "Initial description"},
                headers=headers_a,
            )
            assert create_resp.status_code == 201
            project_id = create_resp.json()["id"]

            # Read project
            get_resp = await client.get(f"/api/v1/projects/{project_id}", headers=headers_a)
            assert get_resp.status_code == 200
            assert get_resp.json()["name"] == "Test Project"

            # Update project
            update_resp = await client.patch(
                f"/api/v1/projects/{project_id}",
                json={"name": "Updated Project"},
                headers=headers_a,
            )
            assert update_resp.status_code == 200
            assert update_resp.json()["name"] == "Updated Project"

            # Delete project
            delete_resp = await client.delete(
                f"/api/v1/projects/{project_id}",
                headers=headers_a,
            )
            assert delete_resp.status_code == 204

            # Verify deleted
            get_deleted = await client.get(f"/api/v1/projects/{project_id}", headers=headers_a)
            assert get_deleted.status_code == 404

        await db.dispose_engine()

    async def test_duplicate_project_name_rejected(self, users_in_tenants):
        """Verify duplicate project names are rejected within a tenant."""
        await db.dispose_engine()
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Login as user A (tenant A)
            login = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": users_in_tenants["user_a"]["email"],
                    "password": users_in_tenants["user_a"]["password"],
                },
                headers={"X-Tenant-Slug": users_in_tenants["tenant_a_slug"]},
            )
            token = login.json()["access_token"]
            headers = {
                "X-Tenant-Slug": users_in_tenants["tenant_a_slug"],
                "Authorization": f"Bearer {token}",
            }

            # Create first project
            resp1 = await client.post(
                "/api/v1/projects",
                json={"name": "Duplicate Name"},
                headers=headers,
            )
            assert resp1.status_code == 201

            # Attempt duplicate - should fail with 409
            resp2 = await client.post(
                "/api/v1/projects",
                json={"name": "Duplicate Name"},
                headers=headers,
            )
            assert resp2.status_code == 409
            assert "already exists" in resp2.json()["detail"].lower()

        await db.dispose_engine()

    async def test_duplicate_project_name_on_update_rejected(self, users_in_tenants):
        """Verify updating a project to a duplicate name is rejected."""
        await db.dispose_engine()
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Login as user A (tenant A)
            login = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": users_in_tenants["user_a"]["email"],
                    "password": users_in_tenants["user_a"]["password"],
                },
                headers={"X-Tenant-Slug": users_in_tenants["tenant_a_slug"]},
            )
            token = login.json()["access_token"]
            headers = {
                "X-Tenant-Slug": users_in_tenants["tenant_a_slug"],
                "Authorization": f"Bearer {token}",
            }

            # Create first project
            resp1 = await client.post(
                "/api/v1/projects",
                json={"name": "First Project"},
                headers=headers,
            )
            assert resp1.status_code == 201

            # Create second project
            resp2 = await client.post(
                "/api/v1/projects",
                json={"name": "Second Project"},
                headers=headers,
            )
            assert resp2.status_code == 201
            project_2_id = resp2.json()["id"]

            # Try to rename second project to first project's name - should fail
            update_resp = await client.patch(
                f"/api/v1/projects/{project_2_id}",
                json={"name": "First Project"},
                headers=headers,
            )
            assert update_resp.status_code == 409
            assert "already exists" in update_resp.json()["detail"].lower()

        await db.dispose_engine()

    async def test_same_project_name_allowed_in_different_tenants(self, users_in_tenants):
        """Verify the same project name can exist in different tenants."""
        await db.dispose_engine()
        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Login as user A (tenant A)
            login_a = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": users_in_tenants["user_a"]["email"],
                    "password": users_in_tenants["user_a"]["password"],
                },
                headers={"X-Tenant-Slug": users_in_tenants["tenant_a_slug"]},
            )
            token_a = login_a.json()["access_token"]

            # Login as user B (tenant B)
            login_b = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": users_in_tenants["user_b"]["email"],
                    "password": users_in_tenants["user_b"]["password"],
                },
                headers={"X-Tenant-Slug": users_in_tenants["tenant_b_slug"]},
            )
            token_b = login_b.json()["access_token"]

            # Create project with same name in tenant A
            resp_a = await client.post(
                "/api/v1/projects",
                json={"name": "Shared Name"},
                headers={
                    "X-Tenant-Slug": users_in_tenants["tenant_a_slug"],
                    "Authorization": f"Bearer {token_a}",
                },
            )
            assert resp_a.status_code == 201

            # Create project with same name in tenant B - should succeed
            resp_b = await client.post(
                "/api/v1/projects",
                json={"name": "Shared Name"},
                headers={
                    "X-Tenant-Slug": users_in_tenants["tenant_b_slug"],
                    "Authorization": f"Bearer {token_b}",
                },
            )
            assert resp_b.status_code == 201

            # Both tenants should have their own project
            assert resp_a.json()["id"] != resp_b.json()["id"]

        await db.dispose_engine()
