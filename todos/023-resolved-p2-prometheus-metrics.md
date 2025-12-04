---
status: ready
priority: p2
issue_id: "023"
tags: [observability, metrics, prometheus, production]
dependencies: []
---

# No Prometheus Metrics / Observability

## Problem Statement
The application has no metrics instrumentation. Cannot monitor API performance, error rates, latency percentiles (p50, p95, p99), or set up alerts for anomalies in production.

## Findings
- Location: Entire project (no metrics implementation)
- No `/metrics` endpoint exposed
- No request duration tracking
- No error rate counters
- No custom business metrics

## Proposed Solutions

### Option 1: Use prometheus-fastapi-instrumentator (Recommended)
```python
from prometheus_fastapi_instrumentator import Instrumentator

def create_app() -> FastAPI:
    app = FastAPI(...)

    # Instrument with Prometheus metrics
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    return app
```

This automatically provides:
- `http_requests_total` - Counter of requests by method, path, status
- `http_request_duration_seconds` - Histogram of request latency
- `http_requests_in_progress` - Gauge of in-flight requests

- **Pros**: Zero-config, automatic instrumentation, standard metrics
- **Cons**: Adds dependency
- **Effort**: Small (< 1 hour)
- **Risk**: Low

### Option 2: Custom metrics with prometheus_client
```python
from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'api_request_duration_seconds',
    'API request duration',
    ['method', 'endpoint']
)

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```
- **Pros**: Full control over metrics
- **Cons**: More code to maintain
- **Effort**: Medium
- **Risk**: Low

## Recommended Action
Implement Option 1 - use prometheus-fastapi-instrumentator for quick setup.

## Technical Details
- **Affected Files**:
  - `src/app/main.py` (add instrumentator)
  - `pyproject.toml` (add prometheus-fastapi-instrumentator)
- **Related Components**: All API endpoints
- **Database Changes**: No

## Resources
- prometheus-fastapi-instrumentator: https://github.com/trallnag/prometheus-fastapi-instrumentator
- Prometheus best practices: https://prometheus.io/docs/practices/naming/

## Acceptance Criteria
- [ ] `/metrics` endpoint exposed with Prometheus format
- [ ] Request count metrics by method/path/status
- [ ] Request duration histogram
- [ ] In-progress request gauge
- [ ] Metrics endpoint excluded from rate limiting
- [ ] Tests pass

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 (Important - Production Readiness)
- Estimated effort: Small

**Learnings:**
- Metrics are essential for production monitoring
- Prometheus is the industry standard for cloud-native apps

## Notes
Source: Triage session on 2025-12-04
