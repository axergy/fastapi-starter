---
status: ready
priority: p3
issue_id: "087"
tags: [performance, memory, pagination, optimization]
dependencies: []
---

# Potential Memory Leak in Pagination

## Problem Statement
Pagination fetches `limit + 1` rows and converts to list immediately. For large limits (up to 100), this loads all rows into memory with complex objects.

## Findings
- Location: `src/app/repositories/base.py:87-88`
- Current code: `items = list(result.scalars().all())`
- Loads all rows into memory at once
- Max limit is 100 items
- Complex objects with relationships increase memory footprint
- High concurrency multiplies impact

## Proposed Solutions

### Option 1: Enforce lower default limits
- **Pros**: Simple, reduces memory per request
- **Cons**: Clients may need more requests
- **Effort**: Small
- **Risk**: Low

```python
# Reduce default max limit
limit: Annotated[int, Query(ge=1, le=50)] = 20  # Was le=100

# Or per-entity limits based on complexity
PAGINATION_LIMITS = {
    "projects": 100,  # Simple entity
    "audit_logs": 50,  # Medium complexity
    "users": 25,      # Complex with relationships
}
```

### Option 2: Use server-side cursors for large datasets
- **Pros**: Constant memory usage regardless of limit
- **Cons**: More complex implementation
- **Effort**: Medium
- **Risk**: Low

```python
async def list_all_streaming(
    self,
    cursor: str | None = None,
    limit: int = 50,
) -> AsyncGenerator[Model, None]:
    """Stream results without loading all into memory."""
    query = select(self.model).limit(limit + 1)
    result = await self.session.stream_scalars(query)
    async for item in result:
        yield item
```

### Option 3: Pagination with projection
- **Pros**: Load only needed fields
- **Cons**: Requires DTO layer
- **Effort**: Medium
- **Risk**: Low

## Recommended Action
Reduce default max limit to 50, add entity-specific limits for complex objects.

## Technical Details
- **Affected Files**: `src/app/repositories/base.py`, endpoint query params
- **Related Components**: All list endpoints
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Default max limit reduced
- [ ] Per-entity limits considered for complex objects
- [ ] Memory usage verified under load
- [ ] Tests updated for new limits
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Pagination limits should account for object complexity
- Streaming alternatives exist for large datasets

## Notes
Source: Triage session on 2025-12-18
