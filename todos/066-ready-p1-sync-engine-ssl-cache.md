---
status: ready
priority: p1
issue_id: "066"
tags: [security, tenant-isolation, temporal, database]
dependencies: []
---

# Missing SSL Configuration for Sync Engine

## Problem Statement
The synchronous engine (used by Temporal workers) doesn't apply SSL settings or disable statement cache. The async engine has `_get_connect_args()` with SSL and `statement_cache_size=0`, but the sync engine used by Temporal activities gets none of these settings.

## Findings
- Location: `src/app/core/db/engine.py:70`
- The sync engine is created with only `pool_pre_ping=True`
- Missing: SSL configuration from `_get_connect_args()`
- Missing: `statement_cache_size=0` which is critical for tenant isolation
- Temporal activities switch `search_path` between tenants frequently

## Proposed Solutions

### Option 1: Apply connect_args to sync engine
- **Pros**: Consistent security settings, prevents cross-tenant data leakage
- **Cons**: None
- **Effort**: Small
- **Risk**: Low

```python
def get_sync_engine() -> Engine:
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        sync_url = settings.database_url.replace("+asyncpg", "")
        connect_args = _get_connect_args()
        _sync_engine = create_engine(
            sync_url,
            pool_pre_ping=True,
            connect_args=connect_args
        )
    return _sync_engine
```

## Recommended Action
Apply `_get_connect_args()` to sync engine to ensure SSL and statement cache settings are consistent.

## Technical Details
- **Affected Files**: `src/app/core/db/engine.py`
- **Related Components**: Temporal workers, tenant activities
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Sync engine uses same connect_args as async engine
- [ ] SSL settings applied when configured
- [ ] Statement cache disabled (size=0)
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Temporal workers use sync engine for activities
- Statement caching with search_path switching can cause cross-tenant data leakage

## Notes
Source: Triage session on 2025-12-18
