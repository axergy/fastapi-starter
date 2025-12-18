---
status: ready
priority: p3
issue_id: "088"
tags: [architecture, observability, health-check, kubernetes]
dependencies: []
---

# Missing Health Check for Database Connectivity

## Problem Statement
Health endpoint may not properly check database connectivity. Kubernetes could route traffic to pods with broken DB connections.

## Findings
- Location: `src/app/core/health.py`
- Health check may be cached or not query DB
- Broken DB connection not detected
- Kubernetes liveness/readiness probes affected
- Traffic routed to non-functional pods

## Proposed Solutions

### Option 1: Add explicit DB health check
- **Pros**: Accurate health status, proper K8s integration
- **Cons**: Adds DB query per health check
- **Effort**: Small
- **Risk**: Low

```python
from sqlalchemy import text
from src.app.core.db import get_session

async def check_database_health() -> tuple[bool, str]:
    """Check database connectivity."""
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as e:
        return False, str(e)

@app.get("/health")
async def health():
    db_healthy, db_status = await check_database_health()
    redis_healthy = await check_redis_health()

    overall_healthy = db_healthy  # DB is required
    status = "healthy" if overall_healthy else "unhealthy"

    return {
        "status": status,
        "database": {"healthy": db_healthy, "status": db_status},
        "redis": {"healthy": redis_healthy, "status": "optional"},
    }

@app.get("/ready")
async def readiness():
    """Readiness probe - check all dependencies."""
    db_healthy, _ = await check_database_health()
    if not db_healthy:
        raise HTTPException(503, "Database unavailable")
    return {"status": "ready"}
```

## Recommended Action
Add explicit database connectivity check to health endpoint, separate liveness and readiness probes.

## Technical Details
- **Affected Files**: `src/app/core/health.py`
- **Related Components**: Kubernetes deployment, monitoring
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- K8s probes: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/

## Acceptance Criteria
- [ ] Health endpoint checks database connectivity
- [ ] Returns unhealthy when DB unavailable
- [ ] Separate readiness probe for K8s
- [ ] Caching doesn't mask DB failures
- [ ] Tests for healthy and unhealthy scenarios
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Health checks must verify actual dependencies
- Kubernetes needs accurate health status for routing

## Notes
Source: Triage session on 2025-12-18
