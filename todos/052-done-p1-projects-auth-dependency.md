---
status: done
priority: p1
issue_id: "052"
tags: [security, authorization, api]
dependencies: []
---

# Projects Endpoints Use Wrong Authorization Dependency

## Problem Statement
Project CRUD endpoints use `AuthenticatedUser` dependency which only validates token existence, NOT tenant membership. The `CurrentUser` dependency includes the critical membership check. This could allow a user with a valid JWT to access project data from ANY tenant.

## Findings
- All project endpoints use `_user: AuthenticatedUser` instead of `_user: CurrentUser`
- Location: `src/app/api/v1/projects.py:30-163`
- `AuthenticatedUser` calls `get_authenticated_user` which does NOT validate tenant membership
- `CurrentUser` calls `get_current_user` which DOES validate membership (auth.py:199-213)

## Proposed Solutions

### Option 1: Replace AuthenticatedUser with CurrentUser
- **Pros**: Simple fix, uses existing validated dependency
- **Cons**: None
- **Effort**: Small (15 minutes)
- **Risk**: Low

## Recommended Action
Replace `_user: AuthenticatedUser` with `_user: CurrentUser` in all four project endpoints:
- `list_projects` (line 30)
- `get_project` (line 53)
- `create_project` (line 78)
- `update_project` (line 107)
- `delete_project` (line 146)

## Technical Details
- **Affected Files**: `src/app/api/v1/projects.py`
- **Related Components**: Authentication dependencies
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- Related: `src/app/api/dependencies/auth.py`

## Acceptance Criteria
- [x] All project endpoints use `CurrentUser` dependency
- [x] Tests pass confirming membership is validated
- [x] User without tenant membership gets 403 Forbidden

## Work Log

### 2025-12-18 - Completed
**By:** Claude Code Assistant
**Actions:**
- Replaced `AuthenticatedUser` with `CurrentUser` in all 5 project endpoints
- Updated import statement in projects.py
- All endpoints now properly validate tenant membership

**Changes:**
- `list_projects` (line 33): `_user: CurrentUser`
- `get_project` (line 56): `_user: CurrentUser`
- `create_project` (line 82): `_user: CurrentUser`
- `update_project` (line 123): `_user: CurrentUser`
- `delete_project` (line 172): `_user: CurrentUser`
- Import updated (line 13): `from src.app.api.dependencies import CurrentUser, TenantDBSession`

### 2025-12-17 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending to ready
- Ready to be picked up and worked on

**Learnings:**
- `AuthenticatedUser` vs `CurrentUser` have different authorization levels
- Tenant-scoped endpoints must always use `CurrentUser`

## Notes
Source: Triage session on 2025-12-17
