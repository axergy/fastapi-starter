---
status: ready
priority: p3
issue_id: "013"
tags: [observability, temporal, kubernetes, health-check]
dependencies: []
---

# Temporal Worker Missing Health Check

## Problem Statement
The Temporal worker runs as a separate process but lacks a health check endpoint, making it difficult to monitor in production. Kubernetes and other orchestrators need health endpoints to manage worker lifecycle and automatically restart unhealthy workers.

## Findings
- Location: `src/app/temporal/worker.py`
- Worker runs as standalone process
- No HTTP endpoint for health checks
- Cannot integrate with K8s liveness/readiness probes
- No visibility into worker health status

**Problem Scenario:**
1. Temporal worker deployed to Kubernetes
2. K8s needs liveness/readiness probes for pod management
3. No HTTP endpoint exists for health checks
4. Cannot determine if worker is healthy or stuck
5. No automatic restart if worker becomes unhealthy
6. Silent failures go undetected

## Proposed Solutions

### Option 1: Lightweight HTTP Health Server
- Add small HTTP server running alongside worker
- Expose `/health` endpoint on separate port (e.g., 8001)
- Report worker status and connection to Temporal server
- **Pros**: Simple, standard K8s integration
- **Cons**: Additional port to manage
- **Effort**: Small (1-2 hours)
- **Risk**: Low

**Implementation:**
```python
import asyncio
from fastapi import FastAPI
import uvicorn

async def run_health_server(port: int = 8001):
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "worker": "running",
            "task_queue": TASK_QUEUE,
        }

    @app.get("/ready")
    async def ready():
        # Could check Temporal connection here
        return {"status": "ready"}

    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    # Run worker and health server concurrently
    async with Worker(...) as worker:
        await asyncio.gather(
            worker.run(),
            run_health_server(),
        )
```

**Kubernetes Config:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8001
  initialDelaySeconds: 10
  periodSeconds: 30
readinessProbe:
  httpGet:
    path: /ready
    port: 8001
  initialDelaySeconds: 5
  periodSeconds: 10
```

## Recommended Action
Implement lightweight HTTP health server alongside Temporal worker

## Technical Details
- **Affected Files**:
  - `src/app/temporal/worker.py`
- **Related Components**: Temporal worker, Kubernetes deployment
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- K8s Probes: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/

## Acceptance Criteria
- [ ] Health endpoint exposed on configurable port
- [ ] `/health` returns worker status
- [ ] `/ready` checks Temporal connection
- [ ] Worker and health server run concurrently
- [ ] Kubernetes deployment config updated with probes
- [ ] Tests verify health endpoints respond correctly

## Work Log

### 2025-12-05 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage session
- Categorized as P3 NICE-TO-HAVE (Observability)
- Estimated effort: Small (1-2 hours)

**Learnings:**
- Long-running processes need health endpoints
- K8s integration requires liveness/readiness probes

## Notes
Source: Triage session on 2025-12-05
Important for production Kubernetes deployments.
