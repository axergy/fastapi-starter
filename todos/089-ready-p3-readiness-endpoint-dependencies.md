---
status: ready
priority: p3
issue_id: "089"
tags: [architecture, observability, kubernetes, readiness]
dependencies: ["088"]
---

# Missing Database Health in Ready Endpoint

## Problem Statement
The readiness endpoint should verify all required dependencies (database, Redis if critical) before accepting traffic. Without this, Kubernetes may route traffic to pods that can't serve requests.

## Findings
- Location: `src/app/core/health.py`
- Readiness may not check all dependencies
- New pods could receive traffic before DB connection established
- Rolling deployments affected
- Service degradation during dependency failures

## Proposed Solutions

### Option 1: Comprehensive readiness check
- **Pros**: Accurate readiness status, safe deployments
- **Cons**: Slightly slower readiness response
- **Effort**: Small
- **Risk**: Low

```python
@app.get("/ready")
async def readiness():
    """
    Readiness probe - verify all required dependencies.

    Used by Kubernetes to determine if pod should receive traffic.
    Returns 503 if any required dependency is unavailable.
    """
    checks = {}

    # Database is required
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "Database unavailable", "checks": checks}
        )

    # Redis is optional but check it
    try:
        redis = await get_redis()
        if redis:
            await redis.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "not configured"
    except Exception:
        checks["redis"] = "unavailable (optional)"

    return {"status": "ready", "checks": checks}

@app.get("/live")
async def liveness():
    """
    Liveness probe - verify process is running.

    Used by Kubernetes to determine if pod should be restarted.
    Should be lightweight - just confirms the process responds.
    """
    return {"status": "alive"}
```

## Recommended Action
Implement separate /ready and /live endpoints with appropriate dependency checks.

## Technical Details
- **Affected Files**: `src/app/core/health.py`
- **Related Components**: Kubernetes deployment manifests
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- Related todo: #088 (health check database)

## Acceptance Criteria
- [ ] /ready endpoint checks database connectivity
- [ ] /live endpoint is lightweight (no DB check)
- [ ] Returns 503 when dependencies unavailable
- [ ] Response includes check details
- [ ] Tests for ready/not ready scenarios
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Liveness and readiness serve different purposes
- Liveness: Is process alive? (restart if not)
- Readiness: Can process serve traffic? (remove from LB if not)

## Notes
Source: Triage session on 2025-12-18
