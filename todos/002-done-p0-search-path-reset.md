---
status: done
priority: p0
issue_id: "002"
tags: [security, database, multi-tenancy, critical]
dependencies: []
---

# Connection Pool Poisoning - Search Path Not Reset

## Problem Statement
`get_tenant_session()` changes the PostgreSQL connection's `search_path` but may fail to reset it before returning the connection to the pool. A subsequent request using that pooled connection could execute queries against the wrong tenant schema, causing data leakage.

## Findings
- `src/app/core/db/session.py`: `get_tenant_session()` sets search_path at connection level
- Reset is in `finally` block at session level, not connection level
- If error occurs between `SET search_path` and session factory creation, connection returns dirty
- `get_public_session()` doesn't explicitly set search_path (trusts pool defaults)
- Pool configuration: `pool_size=5`, `max_overflow=10` with connection reuse

**Race Condition Scenario:**
1. Request 1 sets search_path to `tenant_acme`
2. Exception before session opens
3. Connection returns to pool with `tenant_acme` search_path
4. Request 2 gets same connection, assumes public schema
5. Request 2 queries accidentally access Request 1's tenant data

## Proposed Solutions

### Option 1: Connection-Level try-finally (Recommended)
- **Pros**: Guarantees reset regardless of where error occurs
- **Cons**: Slightly more verbose code
- **Effort**: Small
- **Risk**: Low

**Implementation:**
```python
@asynccontextmanager
async def get_tenant_session(tenant_schema: str, engine: AsyncEngine | None = None):
    validate_schema_name(tenant_schema)
    if engine is None:
        engine = get_engine()

    async with engine.connect() as connection:
        try:
            quoted_schema = await connection.scalar(
                text("SELECT quote_ident(:schema)").bindparams(schema=tenant_schema)
            )
            await connection.execute(text(f"SET search_path TO {quoted_schema}, public"))
            await connection.commit()

            session_factory = async_sessionmaker(bind=connection, ...)
            async with session_factory() as session:
                yield session
        finally:
            # CRITICAL: Always reset before returning to pool
            if not connection.closed:
                await connection.execute(text("SET search_path TO public"))
                await connection.commit()

@asynccontextmanager
async def get_public_session(engine: AsyncEngine | None = None):
    if engine is None:
        engine = get_engine()

    async with engine.connect() as connection:
        # CRITICAL: Explicitly set public path to defend against dirty pooled connections
        await connection.execute(text("SET search_path TO public"))
        # ...
```

## Recommended Action
Wrap entire connection block in try-finally at connection level, and add explicit search_path in `get_public_session()`.

## Technical Details
- **Affected Files**:
  - `src/app/core/db/session.py`
  - `tests/integration/test_critical_paths.py` (new)
- **Related Components**: All tenant-scoped database operations
- **Database Changes**: No

## Resources
- Original finding: Code Review - "Security Risk (Connection Poisoning)"
- Related issues: None

## Acceptance Criteria
- [ ] `get_tenant_session()` resets search_path at connection level in finally block
- [ ] `get_public_session()` explicitly sets `search_path TO public`
- [ ] Integration test verifies search_path is clean after session use
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review analysis
- Categorized as P0 Critical (data leakage risk)
- Estimated effort: Small

**Learnings:**
- Connection pooling with session-scoped state (search_path) requires careful cleanup
- Defensive programming: always assume pooled connections may be dirty

## Notes
Source: Code review analysis on 2025-12-16
