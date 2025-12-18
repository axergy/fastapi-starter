---
status: done
priority: p2
issue_id: "057"
tags: [security, information-disclosure, api, authentication]
dependencies: []
---

# Public Tenant Endpoint Exposes Information Without Auth

## Problem Statement
The `GET /tenants/{slug}` endpoint has NO authentication requirement, allowing anonymous users to enumerate tenant slugs and retrieve tenant metadata (name, status, creation date, ID). This aids reconnaissance for targeted attacks.

## Findings
- Endpoint is completely public, no auth dependency
- Location: `src/app/api/v1/tenants.py:199-207`
- Returns: tenant ID, name, slug, status, created_at
- No rate limiting observed on this specific endpoint
- Enables brute-force slug enumeration

## Proposed Solutions

### Option 1: Require authentication
- **Pros**: Prevents anonymous enumeration
- **Cons**: Legitimate use cases may need public access
- **Effort**: Small (15 minutes)
- **Risk**: Low

### Option 2: Require authentication + membership
- **Pros**: Only members can see tenant details
- **Cons**: May break some workflows
- **Effort**: Small (15 minutes)
- **Risk**: Medium

## Recommended Action
Add `AuthenticatedUser` dependency as minimum protection:

```python
@router.get("/{slug}", response_model=TenantRead)
async def get_tenant(
    slug: str,
    service: TenantServiceDep,
    _user: AuthenticatedUser,  # Add this
) -> TenantRead:
    """Get tenant by slug. Requires authentication."""
    tenant = await service.get_by_slug(slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantRead.model_validate(tenant)
```

Consider also adding rate limiting to prevent enumeration attacks.

## Technical Details
- **Affected Files**: `src/app/api/v1/tenants.py`
- **Related Components**: Authentication dependencies
- **Database Changes**: No

## Resources
- Original finding: Security audit triage session
- OWASP: Information Disclosure vulnerabilities

## Acceptance Criteria
- [x] GET /tenants/{slug} requires authentication
- [x] Anonymous requests return 401 Unauthorized
- [x] Authenticated users can retrieve tenant info
- [x] Tests updated to include auth header (no existing tests found for this endpoint)

## Work Log

### 2025-12-17 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending to ready
- Ready to be picked up and worked on

**Learnings:**
- Public endpoints should be carefully reviewed for information disclosure
- Tenant enumeration can aid targeted attacks
- Defense in depth: auth + rate limiting

### 2025-12-18 - Implemented
**By:** Claude Code
**Actions:**
- Added `_user: AuthenticatedUser` parameter to `get_tenant` function in `src/app/api/v1/tenants.py`
- Updated docstring to note authentication requirement
- No existing tests found for this endpoint to update
- Status changed from ready to done

**Implementation:**
- Authentication now required for GET /tenants/{slug}
- Anonymous requests will return 401 Unauthorized
- Authenticated users can retrieve tenant info as before
- Prevents anonymous tenant enumeration

## Notes
Source: Triage session on 2025-12-17
Completed: 2025-12-18
