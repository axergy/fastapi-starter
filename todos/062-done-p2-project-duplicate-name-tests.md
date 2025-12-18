---
status: done
priority: p2
issue_id: "062"
tags: [testing, quality-assurance, api]
dependencies: ["053"]
---

# Missing Test Coverage for Project Duplicate Name Handling

## Problem Statement
The existing integration tests verify basic CRUD and tenant isolation but don't test duplicate name handling. Once the unique constraint and validation are added (Issue #053), tests should verify the 409 Conflict response.

## Findings
- No test for duplicate project name rejection
- Location: `tests/integration/test_tenant_isolation.py`
- Basic CRUD tests exist but edge cases missing
- API contract for 409 Conflict not enforced

## Proposed Solutions

### Option 1: Add duplicate name test cases
- **Pros**: Ensures API contract, prevents regression
- **Cons**: None
- **Effort**: Small (15 minutes)
- **Risk**: Low

## Recommended Action
Add test case to `test_tenant_isolation.py`:

```python
async def test_duplicate_project_name_rejected(self, users_in_tenants):
    """Verify duplicate project names are rejected within a tenant."""
    await db.dispose_engine()
    app = create_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Login
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

        # Attempt duplicate - should fail
        resp2 = await client.post(
            "/api/v1/projects",
            json={"name": "Duplicate Name"},
            headers=headers,
        )
        assert resp2.status_code == 409
        assert "already exists" in resp2.json()["detail"].lower()

    await db.dispose_engine()
```

Also add test for update conflict scenario.

## Technical Details
- **Affected Files**: `tests/integration/test_tenant_isolation.py`
- **Related Components**: Project API endpoints
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- Depends on: Issue #053 (duplicate name check implementation)

## Acceptance Criteria
- [ ] Test for duplicate name on create returns 409
- [ ] Test for duplicate name on update returns 409
- [ ] Test verifies error message is user-friendly
- [ ] Tests pass with unique constraint in place

## Work Log

### 2025-12-17 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending to ready
- Ready to be picked up and worked on

**Learnings:**
- API contracts should be enforced by tests
- Edge cases like duplicates often missed in initial implementation
- Tests should cover both success and error paths

## Notes
Source: Triage session on 2025-12-17
Depends on: Issue #053 must be implemented first

### 2025-12-18 - Implementation Complete
**By:** Claude
**Actions:**
- Added `test_duplicate_project_name_rejected` test - verifies 409 on create
- Added `test_duplicate_project_name_on_update_rejected` test - verifies 409 on update
- Added `test_same_project_name_allowed_in_different_tenants` test - verifies tenant isolation
- All acceptance criteria met:
  - [x] Test for duplicate name on create returns 409
  - [x] Test for duplicate name on update returns 409
  - [x] Test verifies error message is user-friendly ("already exists" in message)
  - [x] Tests confirm same name allowed in different tenants (tenant isolation)
