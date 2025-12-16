---
status: done
priority: p0
issue_id: "001"
tags: [performance, async, critical]
dependencies: []
---

# Event Loop Blocking in Rate Limiter

## Problem Statement
The global rate limiter uses `threading.Lock()` inside async middleware, which blocks the asyncio event loop. This serializes all requests through the lock, degrading performance to that of a single-threaded synchronous server.

## Findings
- `threading.Lock` imported at `src/app/core/rate_limit.py:13`
- Lock instantiated at `src/app/core/rate_limit.py:28`: `_rate_limit_lock = Lock()`
- Blocking call at `src/app/core/rate_limit.py:129`: `with _rate_limit_lock:`
- The `_check_in_memory_rate_limit()` function is synchronous but called from async middleware
- All concurrent requests serialize through this lock, destroying async benefits

## Proposed Solutions

### Option 1: Replace with asyncio.Lock (Recommended)
- **Pros**: Minimal code change, proper async behavior, non-blocking
- **Cons**: None - this is the correct approach for async code
- **Effort**: Small
- **Risk**: Low

**Implementation:**
```python
import asyncio  # Replace threading import

_rate_limit_lock = asyncio.Lock()  # Use asyncio.Lock

async def _check_in_memory_rate_limit(client_ip: str) -> bool:
    """Check rate limit using in-memory token bucket (async safe)."""
    # ...
    async with _rate_limit_lock:  # Non-blocking await
        # Token bucket logic
```

## Recommended Action
Replace `threading.Lock` with `asyncio.Lock` and make the in-memory rate limit check async.

## Technical Details
- **Affected Files**:
  - `src/app/core/rate_limit.py`
  - `tests/unit/test_rate_limit.py`
- **Related Components**: Global rate limit middleware, in-memory fallback
- **Database Changes**: No

## Resources
- Original finding: Code Review - "Performance Killer (Async Blocking)"
- Related issues: None

## Acceptance Criteria
- [ ] `threading.Lock` replaced with `asyncio.Lock`
- [ ] `_check_in_memory_rate_limit()` is async function
- [ ] Middleware properly awaits the rate limit check
- [ ] Tests updated for async behavior
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review analysis
- Categorized as P0 Critical
- Estimated effort: Small

**Learnings:**
- `threading.Lock` in async code is a common mistake that severely impacts performance
- The Redis path is fine (uses Lua script), only in-memory fallback is affected

## Notes
Source: Code review analysis on 2025-12-16
