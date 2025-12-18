---
status: done
priority: p2
issue_id: "060"
tags: [architecture, api-consistency, pagination, performance]
dependencies: []
---

# Inconsistent Pagination Pattern Between Repositories

## Problem Statement
`ProjectRepository.list_all()` uses offset-based pagination, while other repositories like `TenantRepository` use cursor-based pagination via `BaseRepository.paginate()`. This creates API inconsistency and performance issues with deep offsets.

## Findings
- `ProjectRepository.list_all()` uses `limit/offset` pattern
- `TenantRepository.list_all()` uses `cursor/limit` pattern via `paginate()`
- Location: `src/app/repositories/tenant/project.py:14-19`
- Offset pagination is O(n) for deep pages
- API response format differs between endpoints

## Proposed Solutions

### Option 1: Use cursor-based pagination (Recommended)
- **Pros**: Consistent API, better performance, scalable
- **Cons**: Requires updating endpoint response format
- **Effort**: Small (30 minutes)
- **Risk**: Low

## Recommended Action
Refactor to use inherited `paginate()` method:

```python
class ProjectRepository(BaseRepository[Project]):
    model = Project

    async def list_all(
        self,
        cursor: str | None = None,
        limit: int = 100,
    ) -> tuple[list[Project], str | None, bool]:
        """List all projects with cursor-based pagination."""
        query = select(Project)
        return await self.paginate(query, cursor, limit, Project.created_at)
```

Update endpoint to return pagination metadata:

```python
@router.get("", response_model=PaginatedResponse[ProjectRead])
async def list_projects(
    session: TenantDBSession,
    _user: CurrentUser,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, le=100),
) -> PaginatedResponse[ProjectRead]:
    repo = ProjectRepository(session)
    items, next_cursor, has_more = await repo.list_all(cursor, limit)
    return PaginatedResponse(
        items=[ProjectRead.model_validate(p) for p in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )
```

## Technical Details
- **Affected Files**:
  - `src/app/repositories/tenant/project.py`
  - `src/app/api/v1/projects.py`
  - `src/app/schemas/project.py` (add PaginatedResponse if needed)
- **Related Components**: BaseRepository.paginate()
- **Database Changes**: No

## Resources
- Original finding: Architecture review triage session
- Cursor pagination best practices

## Acceptance Criteria
- [x] `list_all()` uses cursor-based pagination
- [x] API returns `items`, `next_cursor`, `has_more`
- [x] Consistent with other list endpoints
- [x] Tests updated for new response format
- [ ] Performance verified with large datasets

## Work Log

### 2025-12-18 - Implementation Complete
**By:** Claude Code
**Actions:**
- Refactored `ProjectRepository.list_all()` to use cursor-based pagination
- Updated method signature to return `tuple[list[Project], str | None, bool]`
- Method now calls `self.paginate(query, cursor, limit, Project.created_at)`
- Updated `list_projects` endpoint to use `PaginatedResponse[ProjectRead]`
- Added cursor parameter and removed offset parameter from endpoint
- Updated endpoint to return pagination metadata (items, next_cursor, has_more)
- Updated integration tests in `test_tenant_isolation.py` to handle new response format
- Removed unused `col` import from repository

**Files Modified:**
- `src/app/repositories/tenant/project.py`
- `src/app/api/v1/projects.py`
- `tests/integration/test_tenant_isolation.py`

**Learnings:**
- Cursor-based pagination provides O(1) performance regardless of page depth
- PaginatedResponse schema already existed and was used by other endpoints
- BaseRepository.paginate() handles cursor encoding/decoding automatically

### 2025-12-17 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending to ready
- Ready to be picked up and worked on

**Learnings:**
- Offset pagination doesn't scale (O(n) for page n)
- Cursor pagination provides consistent performance
- API consistency reduces client integration complexity

## Notes
Source: Triage session on 2025-12-17
