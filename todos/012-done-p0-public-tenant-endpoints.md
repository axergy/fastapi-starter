---
id: "012"
title: "Public /tenants Endpoints"
status: done
priority: p0
source: "REVIEW.md - CRITICAL #3"
category: security
---

# Public /tenants Endpoints

## Problem

`POST /tenants` and `GET /tenants/status/{slug}` are unauthenticated, enabling abuse vectors:
- Anyone can spam tenant provisioning (resource exhaustion, DoS)
- Tenant enumeration via status endpoint

## Risk

- **Resource exhaustion**: Attackers can create unlimited tenants
- **Temporal queue flooding**: Each tenant triggers workflow execution
- **Database bloat**: Orphan tenant records accumulate
- **Tenant enumeration**: Status endpoint reveals which slugs exist

## Verified Findings

| Location | Line | Issue |
|----------|------|-------|
| `src/app/api/v1/tenants.py` | 40-42 | `create_tenant()` has NO auth dependency |
| `src/app/api/v1/tenants.py` | 100-102 | `get_tenant_status()` has NO auth dependency |

### Current Code

```python
# No authentication required - anyone can create tenants
@router.post("/", response_model=TenantResponse)
async def create_tenant(...):
    ...

# No authentication required - anyone can check tenant status
@router.get("/status/{slug}", response_model=TenantStatusResponse)
async def get_tenant_status(...):
    ...
```

## Fix Options

### Option A: SuperUser Only (Recommended)
Add `SuperUser` dependency to both endpoints. Only platform administrators can create tenants.

```python
@router.post("/", response_model=TenantResponse)
async def create_tenant(
    tenant_data: TenantCreate,
    _: User = Depends(SuperUser),  # Require super user
    ...
):
```

### Option B: Authenticated Users
Add `CurrentUser` dependency - any authenticated user can request a tenant.

### Option C: Public with Strong Rate Limiting
Keep public but add aggressive rate limiting + CAPTCHA for tenant creation.

## Files to Modify

- `src/app/api/v1/tenants.py`
- Tests for tenant endpoints (add auth headers)

## Acceptance Criteria

- [ ] `POST /tenants` requires authentication (SuperUser recommended)
- [ ] `GET /tenants/status/{slug}` either requires auth OR uses unguessable workflow_id instead of slug
- [ ] Tests updated to include authentication headers
- [ ] Unauthorized requests return 401/403
