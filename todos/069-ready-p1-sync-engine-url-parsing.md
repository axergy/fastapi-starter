---
status: ready
priority: p1
issue_id: "069"
tags: [security, database, temporal, validation]
dependencies: []
---

# SQL Injection Risk in Sync Engine URL Conversion

## Problem Statement
The sync engine creation does a simple string replacement without validating the resulting URL. If `database_url` contains `+asyncpg` elsewhere in the string (e.g., in password), replacement corrupts the URL.

## Findings
- Location: `src/app/core/db/engine.py:69`
- Current code: `sync_url = settings.database_url.replace("+asyncpg", "")`
- String replacement is not URL-aware
- Could corrupt URL if pattern appears in credentials or path
- No validation of resulting URL structure

## Proposed Solutions

### Option 1: Use proper URL parsing
- **Pros**: Safe, handles all edge cases, validates structure
- **Cons**: Slightly more code
- **Effort**: Small
- **Risk**: Low

```python
from urllib.parse import urlparse, urlunparse

def get_sync_engine() -> Engine:
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        parsed = urlparse(settings.database_url)
        # Only modify scheme: postgresql+asyncpg -> postgresql
        sync_scheme = parsed.scheme.replace("+asyncpg", "")
        sync_url = urlunparse(parsed._replace(scheme=sync_scheme))
        _sync_engine = create_engine(sync_url, pool_pre_ping=True)
    return _sync_engine
```

## Recommended Action
Replace string replacement with proper URL parsing using `urllib.parse`.

## Technical Details
- **Affected Files**: `src/app/core/db/engine.py`
- **Related Components**: Temporal workers, sync database access
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] URL parsing uses urllib.parse
- [ ] Only scheme is modified, not other URL components
- [ ] Edge cases tested (special chars in password, etc.)
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
- String replacement on URLs is dangerous
- Always use URL-aware parsing for URL manipulation

## Notes
Source: Triage session on 2025-12-18
