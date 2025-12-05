---
status: resolved
priority: p2
issue_id: "010"
tags: [performance, api-design, pagination, developer-experience]
dependencies: []
---

# Implement Unified Cursor-Based Pagination Across All List Endpoints

## Problem Statement
List endpoints return all records without pagination, causing performance issues for large datasets. Need to implement a unified cursor-based pagination system across all endpoints that return lists. Cursor-based pagination is more reliable than offset-based for large datasets (no skipping/duplicates when data changes between requests).

## Findings
- Location: Multiple API endpoints
- No pagination on any list endpoints
- Large responses cause memory pressure and slow API
- Offset-based pagination has issues with concurrent modifications
- No consistent pagination pattern across API
- Already using UUID7 which provides natural time-ordering (can be leveraged for cursors)

**Endpoints Requiring Pagination:**
| Endpoint | Current State |
|----------|--------------|
| `GET /api/v1/tenants` | No pagination |
| `GET /api/v1/admin/tenants` | No pagination |
| `GET /api/v1/invites` | No pagination |
| `GET /api/v1/users/me/tenants` | No pagination |
| Future list endpoints | N/A |

## Proposed Solutions

### Option 1: Unified Cursor-Based Pagination System
- Create reusable pagination utilities
- Use UUID7 `id` as cursor (already time-ordered)
- Consistent API pattern across all endpoints
- Generic response wrapper
- **Pros**: Consistent DX, handles concurrent modifications, efficient for large datasets
- **Cons**: Breaking API change (response structure changes)
- **Effort**: Medium (3-4 hours)
- **Risk**: Low (can version API if needed)

**Pagination Utilities:**
```python
# src/app/schemas/pagination.py
from pydantic import BaseModel, Field
from typing import Generic, TypeVar

T = TypeVar("T")

class PaginationParams(BaseModel):
    """Standard pagination query parameters."""
    cursor: str | None = None  # UUID7 of last item
    limit: int = Field(default=50, ge=1, le=100)

class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response wrapper."""
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False
```

**Repository Helper:**
```python
# src/app/repositories/base.py
async def paginate(
    self,
    query: Select,
    cursor: str | None,
    limit: int,
    order_by_column = "id",  # UUID7 column
) -> tuple[list[T], str | None, bool]:
    if cursor:
        query = query.where(column > cursor)
    query = query.order_by(column).limit(limit + 1)
    results = await self.session.execute(query)
    items = list(results.scalars().all())

    has_more = len(items) > limit
    if has_more:
        items = items[:limit]
    next_cursor = str(items[-1].id) if has_more else None

    return items, next_cursor, has_more
```

**Example API Usage:**
```python
@router.get("", response_model=PaginatedResponse[TenantRead])
async def list_tenants(
    pagination: Annotated[PaginationParams, Depends()],
    service: TenantServiceDep,
) -> PaginatedResponse[TenantRead]:
    items, next_cursor, has_more = await service.list_paginated(
        cursor=pagination.cursor,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
    )
```

**Example Request/Response:**
```
GET /api/v1/tenants?limit=20
GET /api/v1/tenants?limit=20&cursor=0192abc0-...

Response:
{
  "items": [...],
  "next_cursor": "0192abc1-...",
  "has_more": true
}
```

## Recommended Action
Implement unified cursor-based pagination utilities and apply to all list endpoints

## Technical Details
- **Affected Files**:
  - `src/app/schemas/pagination.py` (new)
  - `src/app/repositories/base.py` - Add paginate helper
  - `src/app/api/v1/tenants.py` - Apply pagination
  - `src/app/api/v1/admin.py` - Apply pagination
  - `src/app/api/v1/invites.py` - Apply pagination
  - `src/app/api/v1/users.py` - Apply pagination
  - All corresponding services and repositories
- **Related Components**: All list endpoints, API documentation
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- Cursor Pagination: https://slack.engineering/evolving-api-pagination-at-slack/
- UUID7 Spec: https://www.rfc-editor.org/rfc/rfc9562.html#name-uuid-version-7

## Acceptance Criteria
- [ ] `PaginationParams` schema created with cursor and limit
- [ ] `PaginatedResponse[T]` generic response wrapper created
- [ ] Repository base class has `paginate()` helper method
- [ ] All list endpoints updated to use pagination
- [ ] Default limit set (e.g., 50) with max limit (e.g., 100)
- [ ] OpenAPI docs show pagination parameters and response format
- [ ] Tests verify pagination works correctly (cursor navigation, has_more)
- [ ] Tests verify empty results and single page scenarios

## Work Log

### 2025-12-05 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage session
- Categorized as P2 IMPORTANT (Performance/API Design)
- Estimated effort: Medium (3-4 hours)
- Expanded scope to unified system across all endpoints

**Learnings:**
- Cursor-based pagination is superior to offset for mutable datasets
- UUID7 provides natural time-ordering, perfect for cursors
- Unified approach ensures consistent developer experience

## Notes
Source: Triage session on 2025-12-05
This is a breaking API change - consider versioning or migration strategy.
