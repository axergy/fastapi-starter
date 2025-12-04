---
status: ready
priority: p2
issue_id: "005"
tags: [data-integrity, transactions, error-handling]
dependencies: []
---

# Missing Database Transaction Rollback in Error Paths

## Problem Statement
Database operations can fail after `session.commit()` without proper rollback handling. If commit fails or subsequent operations fail, the session remains in a dirty state, potentially causing data inconsistencies.

## Findings
- No explicit rollback in error paths
- Location: `src/app/services/auth_service.py:92`
- Affects various service methods that modify data
- Session left in dirty state on commit failure
- Can cause data inconsistencies or cascading failures

## Proposed Solutions

### Option 1: Add try/except with rollback to all mutating service methods (RECOMMENDED)
- **Pros**: Explicit error handling, clean session state on failure
- **Cons**: Verbose, needs to be applied consistently
- **Effort**: Medium (3-4 hours)
- **Risk**: Low

Implementation:
```python
async def authenticate(self, email: str, password: str) -> LoginResponse | None:
    try:
        # ... validation and business logic ...

        self.token_repo.add(db_token)
        await self.session.commit()

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )
    except Exception:
        await self.session.rollback()
        raise
```

### Option 2: Create a context manager/decorator for transaction handling
- **Pros**: DRY, consistent handling across all methods
- **Cons**: More complex initial implementation
- **Effort**: Medium (4-5 hours)
- **Risk**: Low

## Recommended Action
Implement Option 1 for immediate fix, consider Option 2 as future refactor

## Technical Details
- **Affected Files**:
  - `src/app/services/auth_service.py`
  - `src/app/services/tenant_service.py`
  - `src/app/services/registration_service.py`
  - Any other services with database mutations
- **Related Components**: All database operations
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- SQLAlchemy session management: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html

## Acceptance Criteria
- [ ] All service methods with commits wrapped in try/except
- [ ] Rollback called on any exception
- [ ] Original exception re-raised after rollback
- [ ] Tests for rollback behavior on failures
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 IMPORTANT
- Estimated effort: Medium (3-4 hours)

**Learnings:**
- Explicit transaction management prevents dirty session states
- Consider decorator pattern for consistent handling

## Notes
Source: Triage session on 2025-12-04
