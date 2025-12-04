---
status: ready
priority: p2
issue_id: "022"
tags: [observability, logging, production, structlog]
dependencies: []
---

# No Structured JSON Logging for Production

## Problem Statement
Current logging uses human-readable format which is difficult to parse, search, and aggregate in production log management systems (ELK, Datadog, CloudWatch, etc.). Need to implement structlog for production-ready structured logging.

## Findings
- Location: `src/app/core/logging.py`
- Current format: `'%(asctime)s [%(correlation_id)s] %(name)s - %(levelname)s - %(message)s'`
- Human-readable but not machine-parseable
- No JSON output for log aggregation systems

## Proposed Solutions

### Option 1: Implement structlog (Recommended)
```python
import structlog
from structlog.stdlib import ProcessorStack

def setup_logging(debug: bool = False) -> None:
    """Configure structlog for structured logging."""

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if debug:
        # Human-readable output for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # JSON output for production
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Usage:
logger = structlog.get_logger()
logger.info("user_login", user_id=user_id, tenant_id=tenant_id)
```
- **Pros**: Industry standard, context binding, JSON output, great dev experience
- **Cons**: Need to add structlog dependency
- **Effort**: Small (< 1 hour)
- **Risk**: Low

## Recommended Action
Implement Option 1 - use structlog with JSON output in production, console renderer in dev.

## Technical Details
- **Affected Files**:
  - `src/app/core/logging.py` (rewrite)
  - `pyproject.toml` (add structlog dependency)
  - Various files using logging (update to use structlog)
- **Related Components**: All components that log
- **Database Changes**: No

## Resources
- structlog documentation: https://www.structlog.org/
- structlog FastAPI integration: https://www.structlog.org/en/stable/frameworks.html

## Acceptance Criteria
- [ ] structlog configured with JSON output for production
- [ ] Console renderer used in debug mode for readability
- [ ] Correlation ID automatically included in all logs
- [ ] Tenant ID and user ID bound to logger context where available
- [ ] Existing log calls migrated to structlog
- [ ] Tests pass

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 (Important - Production Readiness)
- User specified structlog as preferred solution
- Estimated effort: Small

**Learnings:**
- Structured logging is essential for production observability
- structlog provides excellent developer experience with context binding

## Notes
Source: Triage session on 2025-12-04
Use structlog (not python-json-logger) as specified by user.
