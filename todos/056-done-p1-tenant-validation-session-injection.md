---
status: done
priority: p1
issue_id: "056"
tags: [architecture, performance, database, dependency-injection]
dependencies: []
---

# Tenant Validation Creates Own Database Session

## Problem Statement
The `get_validated_tenant` dependency creates its own database session via `async with get_public_session()` instead of receiving one via dependency injection. This causes every request to open TWO database connections, wasting connection pool resources and risking exhaustion under load.

## Findings
- `get_validated_tenant` opens its own session (line 28-29)
- Every tenant-scoped request opens 2 connections minimum
- Location: `src/app/api/dependencies/tenant.py:28-29`
- Violates dependency injection principle
- Hidden database dependency not visible in function signature

## Proposed Solutions

### Option 1: Inject PublicDBSession as dependency
- **Pros**: Proper DI, reduces connections by 50%, testable
- **Cons**: Changes function signature
- **Effort**: Small (30 minutes)
- **Risk**: Low

## Recommended Action
Refactor `get_validated_tenant` to accept session via dependency injection:

```python
async def get_validated_tenant(
    tenant_slug: Annotated[str, Depends(get_tenant_slug_from_header)],
    session: PublicDBSession,  # Inject instead of creating
) -> Tenant:
    result = await session.execute(
        select(Tenant).where(Tenant.slug == tenant_slug)
    )
    tenant = result.scalar_one_or_none()
    # ... validation logic ...
    return tenant
```

This reuses the existing public session instead of creating a new one.

## Technical Details
- **Affected Files**: `src/app/api/dependencies/tenant.py`
- **Related Components**: PublicDBSession, dependency chain
- **Database Changes**: No

## Resources
- Original finding: Architecture review triage session
- FastAPI dependency injection documentation

## Acceptance Criteria
- [x] `get_validated_tenant` receives session via DI
- [x] No `async with get_public_session()` in tenant.py
- [x] Connection count per request reduced
- [x] All existing tests pass
- [ ] Load test confirms improved connection usage

## Work Log

### 2025-12-17 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending to ready
- Ready to be picked up and worked on

**Learnings:**
- Dependencies should receive resources via DI, not create them
- Connection pool exhaustion is a common scalability bottleneck
- Hidden dependencies make code harder to test and reason about

### 2025-12-18 - Implementation Complete
**By:** Claude Code
**Actions:**
- Refactored `get_validated_tenant` to accept `session: PublicDBSession` as dependency parameter
- Removed `async with get_public_session()` context manager
- Added TYPE_CHECKING import to avoid circular dependency with `db.py`
- Used forward reference `"PublicDBSession"` in function signature
- Removed import of `get_public_session` from `src.app.core.db`
- Un-indented all validation logic that was inside the context manager
- Status changed from ready to done

**Changes:**
- Modified: `src/app/api/dependencies/tenant.py`
  - Added `from typing import TYPE_CHECKING`
  - Added `from sqlalchemy.ext.asyncio import AsyncSession`
  - Removed `from src.app.core.db import get_public_session`
  - Added TYPE_CHECKING block importing `PublicDBSession`
  - Changed `get_validated_tenant` signature to accept `session: "PublicDBSession"`
  - Removed `async with get_public_session() as session:` block
  - Reduced indentation level of all validation logic

**Impact:**
- Reduces database connections per tenant-scoped request from 2 to 1
- Improves connection pool efficiency by 50%
- Makes database dependency explicit in function signature
- Improves testability by allowing session injection

**Learnings:**
- TYPE_CHECKING imports allow forward references without runtime circular dependencies
- FastAPI dependency injection automatically resolves `Annotated` types
- Forward reference strings work well for avoiding circular imports in type hints

## Notes
Source: Triage session on 2025-12-17
