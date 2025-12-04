---
status: ready
priority: p2
issue_id: "011"
tags: [security, authorization, multi-tenancy]
dependencies: []
---

# Missing Tenant Isolation Validation in Endpoints

## Problem Statement
The tenant listing endpoint returns ALL tenants to any authenticated user, regardless of their memberships. This is an information disclosure vulnerability - users can see tenants they don't belong to.

## Findings
- GET /api/v1/tenants returns all tenants
- Location: `src/app/api/v1/tenants.py:68-84`
- No filtering by user's memberships
- Information disclosure vulnerability
- Enables tenant enumeration attacks

## Proposed Solutions

### Option 1: Filter by user's memberships (RECOMMENDED)
- **Pros**: Proper access control, follows principle of least privilege
- **Cons**: Requires membership lookup
- **Effort**: Medium (2 hours)
- **Risk**: Low

Implementation:
```python
@router.get("", response_model=list[TenantRead])
async def list_tenants(
    current_user: CurrentUser,
    service: TenantServiceDep,
    membership_repo: MembershipRepoDep,
) -> list[TenantRead]:
    """List tenants where current user has membership."""
    # Get user's tenant memberships
    memberships = await membership_repo.list_user_tenants(current_user.id)
    tenant_ids = {m.tenant_id for m in memberships}

    # Filter tenants
    all_tenants = await service.list_tenants()
    user_tenants = [t for t in all_tenants if t.id in tenant_ids]

    return [TenantRead.model_validate(t) for t in user_tenants]
```

### Option 2: Remove endpoint entirely
- **Pros**: Eliminates risk completely
- **Cons**: May break functionality if endpoint is needed
- **Effort**: Small (30 minutes)
- **Risk**: Medium - may break clients

## Recommended Action
Implement Option 1 - filter by user's memberships

## Technical Details
- **Affected Files**:
  - `src/app/api/v1/tenants.py`
  - May need new repository method for membership lookup
- **Related Components**: Authentication, membership system
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- OWASP Access Control: https://cheatsheetseries.owasp.org/cheatsheets/Access_Control_Cheat_Sheet.html

## Acceptance Criteria
- [ ] Endpoint requires authentication
- [ ] Only returns tenants where user has membership
- [ ] Empty list returned if user has no memberships
- [ ] Tests for isolation behavior
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 IMPORTANT
- Estimated effort: Medium (2 hours)

**Learnings:**
- Multi-tenant systems require careful access control at every endpoint
- Default to restrictive access, not permissive

## Notes
Source: Triage session on 2025-12-04
