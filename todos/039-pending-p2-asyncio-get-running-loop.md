---
status: done
priority: p2
issue_id: "039"
tags: [testing, async, deprecation, python]
dependencies: []
---

# Replace Deprecated asyncio.get_event_loop() Pattern

## Problem Statement
The async test fixtures use the deprecated `asyncio.get_event_loop()` pattern. In modern Python (3.10+), this pattern is increasingly brittle and can warn/fail depending on asyncio policy. Inside an async fixture, you should use the running loop instead.

## Findings
- Location: `tests/integration/conftest.py`

- Line 61:
  ```python
  loop = asyncio.get_event_loop()
  ```

- Line 99:
  ```python
  loop = asyncio.get_event_loop()
  ```

- Line 127:
  ```python
  loop = asyncio.get_event_loop()
  ```

- Current pattern used:
  ```python
  loop = asyncio.get_event_loop()
  with ThreadPoolExecutor(max_workers=1) as pool:
      await loop.run_in_executor(pool, run_migrations_sync, ...)
  ```

- This pattern can cause `DeprecationWarning` or unexpected behavior in newer Python versions

## Proposed Solutions

### Option 1: Use asyncio.to_thread() (Recommended)
- **Pros**: Cleaner, modern Python 3.9+ pattern, less ceremony
- **Cons**: None
- **Effort**: Small
- **Risk**: Low

```python
# Instead of:
loop = asyncio.get_event_loop()
with ThreadPoolExecutor(max_workers=1) as pool:
    await loop.run_in_executor(pool, run_migrations_sync, str(db_url))

# Use:
await asyncio.to_thread(run_migrations_sync, str(db_url))
```

### Option 2: Use asyncio.get_running_loop()
- **Pros**: Still works with explicit executor control
- **Cons**: More verbose than to_thread
- **Effort**: Small
- **Risk**: Low

```python
loop = asyncio.get_running_loop()
with ThreadPoolExecutor(max_workers=1) as pool:
    await loop.run_in_executor(pool, run_migrations_sync, str(db_url))
```

## Recommended Action
Implement Option 1 - use `asyncio.to_thread()` for a cleaner, more modern approach.

## Technical Details
- **Affected Files**: `tests/integration/conftest.py`
- **Related Components**: Test fixtures, async test infrastructure
- **Database Changes**: No

## Resources
- Original finding: REVIEW2.md - Medium #7
- Python docs: https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
- Related issues: None

## Acceptance Criteria
- [ ] Line 61 updated to use asyncio.to_thread()
- [ ] Line 99 updated to use asyncio.to_thread()
- [ ] Line 127 updated to use asyncio.to_thread()
- [ ] ThreadPoolExecutor context managers removed (no longer needed)
- [ ] Tests pass
- [ ] No deprecation warnings in test output
- [ ] Code reviewed

## Work Log

### 2025-12-17 - Completed
**By:** Claude Code Assistant
**Actions:**
- Replaced all three `asyncio.get_event_loop()` calls with `asyncio.to_thread()`
- Removed deprecated ThreadPoolExecutor context managers
- Removed unused `from concurrent.futures import ThreadPoolExecutor` import
- Updated todo status to done

**Changes:**
- Line 61: Replaced loop.run_in_executor with asyncio.to_thread
- Line 97: Replaced loop.run_in_executor with asyncio.to_thread
- Line 123: Replaced loop.run_in_executor with asyncio.to_thread
- Removed ThreadPoolExecutor import from line 9

**Learnings:**
- Modern asyncio.to_thread() pattern is cleaner and more maintainable
- Eliminates deprecation warnings in Python 3.10+
- Reduces boilerplate code significantly

### 2024-12-17 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW2.md code review
- Categorized as MEDIUM (future compatibility)
- Estimated effort: Small

**Learnings:**
- asyncio.get_event_loop() is deprecated for getting loop inside async context
- asyncio.to_thread() is the modern, cleaner alternative for sync-in-async

## Notes
Source: REVIEW2.md Medium #7
