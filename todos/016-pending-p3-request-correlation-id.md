---
status: ready
priority: p3
issue_id: "016"
tags: [observability, logging, debugging]
dependencies: []
---

# Missing Request ID Tracking

## Problem Statement
No way to track requests across logs, making debugging distributed issues difficult. No correlation ID passed between services.

## Findings
- No request ID/correlation ID middleware
- Location: All API endpoints
- Logs from different requests interleaved
- Cannot trace request flow through system
- Difficult to debug user-reported errors

## Proposed Solutions

### Option 1: Use asgi-correlation-id library (RECOMMENDED)
- **Pros**: Battle-tested, integrates with logging, handles propagation
- **Cons**: Additional dependency
- **Effort**: Small (1 hour)
- **Risk**: Low

Implementation:
```python
# Install: pip install asgi-correlation-id

# In main.py
from asgi_correlation_id import CorrelationIdMiddleware
from asgi_correlation_id.context import correlation_id

app.add_middleware(CorrelationIdMiddleware)

# In logging config - add correlation_id to format
import logging
from asgi_correlation_id import correlation_id

class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = correlation_id.get() or "-"
        return True

# Format: '%(asctime)s [%(correlation_id)s] %(levelname)s %(message)s'
```

Library: https://github.com/snok/asgi-correlation-id

## Recommended Action
Implement Option 1 - use asgi-correlation-id library

## Technical Details
- **Affected Files**:
  - `src/app/main.py`
  - `src/app/core/logging.py` (if exists)
  - `pyproject.toml` (add dependency)
- **Related Components**: All API endpoints, logging
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- asgi-correlation-id: https://github.com/snok/asgi-correlation-id

## Acceptance Criteria
- [ ] asgi-correlation-id dependency added
- [ ] CorrelationIdMiddleware added to app
- [ ] X-Request-ID header returned in responses
- [ ] Correlation ID included in all log entries
- [ ] Incoming X-Request-ID header respected
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P3 NICE-TO-HAVE
- Estimated effort: Small (1 hour)

**Learnings:**
- Correlation IDs essential for distributed tracing
- Use proven library rather than custom implementation

## Notes
Source: Triage session on 2025-12-04
