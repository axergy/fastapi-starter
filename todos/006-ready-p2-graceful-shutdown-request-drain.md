---
status: ready
priority: p2
issue_id: "006"
tags: [architecture, availability, kubernetes, deployment]
dependencies: []
---

# Graceful Shutdown Blocks New Requests

## Problem Statement
The shutdown handler uses `await asyncio.sleep(grace_period)` which blocks for 30 seconds during shutdown. This doesn't actually "drain" requests - it just delays cleanup. The application cannot process any new health checks during this time, causing load balancers to mark the instance as unhealthy immediately during rolling deployments.

## Findings
- Location: `src/app/main.py:38-49`
- Current implementation just sleeps, doesn't track in-flight requests
- Health checks fail during the sleep period
- No mechanism to wait for actual request completion

**Problem Scenario:**
1. Kubernetes sends SIGTERM to initiate graceful shutdown
2. App starts 30-second sleep (doesn't accept new requests)
3. Load balancer health check fails immediately
4. Load balancer removes instance from pool
5. In-flight requests may not complete properly
6. Rolling deployments appear unhealthy

**Current Code:**
```python
# Allow in-flight requests to complete
await asyncio.sleep(grace_period)  # Blocks everything for 30s
```

## Proposed Solutions

### Option 1: Implement Request Tracking with Proper Drain
- Add middleware to track in-flight request count
- Continue serving health checks during drain (return "draining" status)
- Wait for actual requests to complete (with timeout)
- Then close connections
- **Pros**: Proper graceful shutdown, zero-downtime deployments
- **Cons**: More complex implementation
- **Effort**: Medium (3-4 hours)
- **Risk**: Low

**Proposed Implementation:**
```python
class RequestTracker:
    def __init__(self):
        self.in_flight = 0
        self.shutting_down = False
        self._lock = asyncio.Lock()

async def shutdown_handler():
    tracker.shutting_down = True
    # Wait for in-flight requests (with timeout)
    await wait_for_requests(timeout=settings.shutdown_grace_period)
```

## Recommended Action
Implement request tracking middleware with proper drain logic

## Technical Details
- **Affected Files**:
  - `src/app/main.py`
  - New middleware for request tracking
- **Related Components**: Lifespan management, health checks
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- Kubernetes graceful shutdown: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination

## Acceptance Criteria
- [ ] Middleware tracks in-flight request count
- [ ] Health endpoint returns "draining" during shutdown
- [ ] Shutdown waits for actual requests to complete
- [ ] Timeout prevents indefinite waiting
- [ ] Rolling deployment shows zero failed health checks
- [ ] Tests verify graceful shutdown behavior

## Work Log

### 2025-12-05 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage session
- Categorized as P2 IMPORTANT (Availability)
- Estimated effort: Medium (3-4 hours)

**Learnings:**
- `asyncio.sleep()` is not proper request draining
- Load balancers need health checks to work during drain period

## Notes
Source: Triage session on 2025-12-05
Important for production Kubernetes deployments.
