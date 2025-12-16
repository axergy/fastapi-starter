---
status: done
priority: p1
issue_id: "004"
tags: [audit, observability, database, transaction]
dependencies: []
---

# Audit Logs Lost on Transaction Rollback

## Problem Statement
Audit logs share the same database session/transaction as business logic. If an operation errors and the transaction rolls back, the audit log of that failure is also lost. This creates an observability gap where failed operations leave no trace.

## Findings
- `src/app/api/dependencies/services.py:113-119`: Same `DBSession` injected to both services
- `src/app/services/audit_service.py:99`: `await self.session.commit()` commits shared session
- Business logic and audit use the same session instance
- If business logic rolls back after audit logs, the audit is lost
- If audit commits first, it may auto-flush pending business changes

**Scenario - Registration Failure:**
```
1. RegistrationService.register_user() starts transaction
2. Creates user record in session (not committed)
3. Email verification fails (external service error)
4. service.register_user() raises exception
5. await audit_service.log_failure() is called
6. audit_service commits the session -> User record gets committed anyway!
7. Inconsistent state: user created but registration "failed"
```

**Alternate Scenario - Rollback Before Audit:**
```
1. Business operation fails
2. Session.rollback() called
3. audit_service.log_failure() tries to commit
4. Nothing to commit - audit log lost
```

## Proposed Solutions

### Option 1: Dedicated Session for AuditService (Recommended)
- **Pros**: Complete isolation, audit logs always persisted, no interference
- **Cons**: Requires creating separate session factory
- **Effort**: Medium
- **Risk**: Low

**Implementation:**
```python
# src/app/api/dependencies/services.py

from src.app.core.db.session import get_engine

async def get_audit_service(
    tenant: ValidatedTenant,
) -> AsyncGenerator[AuditService, None]:
    """Get audit service with its own isolated session."""
    engine = get_engine()
    # Create a dedicated session for auditing (commits independently)
    async with AsyncSession(engine) as session:
        repo = AuditLogRepo(session)
        yield AuditService(repo, session, tenant.id)
```

## Recommended Action
Give AuditService its own dedicated database session that commits independently from business transactions.

## Technical Details
- **Affected Files**:
  - `src/app/api/dependencies/services.py`
  - `src/app/services/audit_service.py` (verify it handles its own commits)
  - `tests/integration/test_critical_paths.py` (new test)
- **Related Components**: All endpoints that use audit logging
- **Database Changes**: No

## Resources
- Original finding: Code Review - "Observability Gap"
- Related issues: None

## Acceptance Criteria
- [ ] AuditService receives dedicated session, not shared DBSession
- [ ] Audit logs commit independently from business transactions
- [ ] Test verifies audit log persists even when business operation fails
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review analysis
- Categorized as P1 High (observability gap)
- Estimated effort: Medium

**Learnings:**
- Side-effect logging should be decoupled from main transaction
- "Fire-and-forget" audit pattern requires independent session
- Consider async queue for audit logs in high-throughput scenarios

## Notes
Source: Code review analysis on 2025-12-16
