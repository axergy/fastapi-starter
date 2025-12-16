---
id: "010"
title: "Statement Cache Cross-Tenant Isolation"
status: pending
priority: p0
source: "REVIEW.md - CRITICAL #1"
category: security
---

# Statement Cache Cross-Tenant Isolation

## Problem

Pooled connections + search_path switching + asyncpg statement cache can cause cross-tenant prepared statement reuse. When a connection is returned to the pool after serving Tenant A, and then assigned to Tenant B with a different search_path, cached prepared statements may execute against the wrong schema.

## Risk

- **Cross-tenant data leakage**: Prepared statements compiled for Tenant A's schema could execute against Tenant B's schema
- **Security bypass**: Row-level security based on search_path becomes ineffective
- **Silent data corruption**: INSERTs/UPDATEs may go to wrong tenant schema

## Verified Findings

| Location | Line | Issue |
|----------|------|-------|
| `src/app/core/config.py` | - | NO `database_statement_cache_size` setting exists |
| `src/app/core/db/engine.py` | 16-29 | `_get_connect_args()` does NOT include `statement_cache_size` |
| `src/app/core/db/engine.py` | 46 | `pool_pre_ping=True` IS present (good) but insufficient |

## Fix

1. Add `database_statement_cache_size: int = 0` to config (disable statement cache)
2. Pass `statement_cache_size` to asyncpg connect_args in engine.py

### Code Changes

**src/app/core/config.py:**
```python
# Add to Settings class
database_statement_cache_size: int = 0  # Disable for multi-tenant safety
```

**src/app/core/db/engine.py:**
```python
def _get_connect_args() -> dict[str, Any]:
    settings = get_settings()
    args: dict[str, Any] = {
        "statement_cache_size": settings.database_statement_cache_size,
    }
    # ... existing SSL handling
    return args
```

## Files to Modify

- `src/app/core/config.py`
- `src/app/core/db/engine.py`

## Acceptance Criteria

- [ ] `database_statement_cache_size` config option added with default 0
- [ ] `statement_cache_size` passed to asyncpg in connect_args
- [ ] Unit test verifies connect_args includes statement_cache_size
- [ ] Documentation comment explains why cache is disabled
