---
status: ready
priority: p2
issue_id: "024"
tags: [production, reliability, kubernetes, shutdown]
dependencies: []
---

# No Graceful Shutdown Handling

## Problem Statement
The application lifespan handler doesn't wait for in-flight requests to complete before shutting down. During deployments or restarts, active requests may be terminated mid-execution, causing data corruption or failed transactions.

## Findings
- Location: `src/app/main.py:24-35`
- Current lifespan immediately disposes resources on shutdown
- No drain period for in-flight requests
- No signal handling for SIGTERM/SIGINT

## Proposed Solutions

### Option 1: Add graceful shutdown with configurable drain period (Recommended)
```python
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_logging(settings.debug)
    logger.info(f"Starting {settings.app_name}")

    yield

    # Graceful shutdown
    grace_period = getattr(settings, 'shutdown_grace_period', 30)
    logger.info(f"Shutdown initiated, draining requests for {grace_period}s...")

    # Allow in-flight requests to complete
    await asyncio.sleep(grace_period)

    logger.info("Closing connections...")
    await close_temporal_client()
    await dispose_engine()
    logger.info("Shutdown complete")
```

Add to config:
```python
shutdown_grace_period: int = 30  # seconds
```

- **Pros**: Allows in-flight requests to complete, configurable
- **Cons**: Extends shutdown time
- **Effort**: Small (< 1 hour)
- **Risk**: Low

### Option 2: Use uvicorn's built-in graceful shutdown
Configure uvicorn with `--timeout-graceful-shutdown 30` flag.
- **Pros**: No code changes
- **Cons**: Depends on deployment configuration
- **Effort**: Small
- **Risk**: Low

## Recommended Action
Implement Option 1 - add graceful shutdown in lifespan with configurable drain period.

## Technical Details
- **Affected Files**:
  - `src/app/main.py` (lifespan function)
  - `src/app/core/config.py` (add shutdown_grace_period setting)
- **Related Components**: Uvicorn, Kubernetes deployment
- **Database Changes**: No

## Resources
- FastAPI Lifespan: https://fastapi.tiangolo.com/advanced/events/
- Kubernetes Graceful Shutdown: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination

## Acceptance Criteria
- [ ] Configurable shutdown grace period in settings
- [ ] Lifespan waits for grace period before disposing resources
- [ ] Shutdown logs clearly indicate draining phase
- [ ] In-flight requests complete during grace period
- [ ] Tests pass

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 (Important - Production Readiness)
- Estimated effort: Small

**Learnings:**
- Graceful shutdown prevents request failures during deployments
- Kubernetes sends SIGTERM and expects apps to handle gracefully

## Notes
Source: Triage session on 2025-12-04
