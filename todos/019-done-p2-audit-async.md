---
id: "019"
title: "Audit Logging Async Option"
status: done
priority: p2
source: "REVIEW.md - MEDIUM #11"
category: performance
---

# Audit Logging Async Option

## Problem

Audit logging is always synchronous, adding latency to every request. For high-volume endpoints, this can significantly impact response times.

## Risk

- **Latency**: Each request waits for audit INSERT + COMMIT
- **Cascading failures**: DB slowdown affects all requests
- **Scalability limit**: Audit writes become bottleneck

## Verified Findings

| Location | Line | Issue |
|----------|------|-------|
| `src/app/services/audit_service.py` | 98-99 | Always commits synchronously |
| `src/app/core/config.py` | - | No configuration for async audit modes |

### Current Flow

```
Request → Handler → Audit INSERT → COMMIT → Response
                    ^^^^^^^^^^^^^^^^^^^^
                    Blocking latency added
```

### Desired Flow (Async Mode)

```
Request → Handler → Queue Audit → Response
                    (non-blocking)
          Background Worker → INSERT → COMMIT
```

## Fix (Future Enhancement)

Add configurable audit modes:
1. **sync** (current): Immediate INSERT + COMMIT
2. **async**: Queue to Redis/Temporal for background processing
3. **sampled**: Log only X% of events (for very high volume)

### Code Changes

**src/app/core/config.py:**
```python
class Settings(BaseSettings):
    audit_mode: Literal["sync", "async", "sampled"] = "sync"
    audit_sample_rate: float = 1.0  # For sampled mode: 0.0-1.0
```

**src/app/services/audit_service.py:**
```python
async def log_event(self, event: AuditEvent) -> None:
    if settings.audit_mode == "sync":
        await self._log_sync(event)
    elif settings.audit_mode == "async":
        await self._queue_async(event)  # Push to Redis queue
    elif settings.audit_mode == "sampled":
        if random.random() < settings.audit_sample_rate:
            await self._log_sync(event)
```

## Files to Modify

- `src/app/core/config.py`
- `src/app/services/audit_service.py`
- New: Background worker for async audit processing

## Acceptance Criteria

- [ ] `audit_mode` config option added (sync/async/sampled)
- [ ] Sync mode works exactly as current behavior
- [ ] Async mode queues events without blocking response
- [ ] Sampled mode respects sample_rate configuration
- [ ] Documentation for each mode and when to use it
