---
status: ready
priority: p3
issue_id: "083"
tags: [performance, cors, network, optimization]
dependencies: []
---

# Missing CORS Preflight Cache

## Problem Statement
CORS configuration likely doesn't set `max_age` for preflight responses, causing unnecessary OPTIONS requests on every API call from browsers.

## Findings
- Location: CORS middleware configuration
- No `max_age` parameter set
- Preflight requests not cached by browser
- Every cross-origin request triggers OPTIONS first
- Doubles latency for all frontend API calls

## Proposed Solutions

### Option 1: Add max_age to CORS configuration
- **Pros**: Simple one-line fix, significant performance improvement
- **Cons**: None
- **Effort**: Small
- **Risk**: Low

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,  # Cache preflight for 1 hour
)
```

## Recommended Action
Add `max_age=3600` to CORS middleware configuration.

## Technical Details
- **Affected Files**: `src/app/api/middlewares/__init__.py` or `src/app/main.py`
- **Related Components**: All cross-origin API requests
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- MDN CORS docs: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS

## Acceptance Criteria
- [ ] CORS max_age configured
- [ ] Preflight responses include Access-Control-Max-Age header
- [ ] Browser caches preflight responses
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
- Preflight caching significantly reduces latency for SPAs
- Small configuration change, big performance win

## Notes
Source: Triage session on 2025-12-18
