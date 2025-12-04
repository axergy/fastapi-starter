---
status: ready
priority: p3
issue_id: "013"
tags: [observability, logging, monitoring]
dependencies: []
---

# Missing Logging Infrastructure

## Problem Statement
The application uses `print()` statements instead of structured logging. No centralized logging configuration, log levels, or structured logs for monitoring.

## Findings
- print() statements used instead of logging
- Location: `main.py:16`, `main.py:20`, `worker.py:44`
- No log levels (debug, info, warning, error)
- No structured logging for log aggregation
- Difficult to debug production issues

## Proposed Solutions

### Option 1: Implement Python logging with configuration (RECOMMENDED)
- **Pros**: Standard library, log levels, configurable format
- **Cons**: Initial setup required
- **Effort**: Small (2 hours)
- **Risk**: Low

Implementation:
```python
# src/app/core/logging.py
import logging
import sys

def setup_logging(debug: bool = False) -> None:
    """Configure application logging."""
    log_level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # Set library log levels
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("temporalio").setLevel(logging.INFO)

# In main.py
import logging
logger = logging.getLogger(__name__)

logger.info(f"Starting {settings.app_name}")
```

### Option 2: Use structlog for JSON logging
- **Pros**: Structured JSON output, better for log aggregation
- **Cons**: Additional dependency
- **Effort**: Medium (3-4 hours)
- **Risk**: Low

## Recommended Action
Implement Option 1 for simplicity, consider Option 2 for production

## Technical Details
- **Affected Files**:
  - New file: `src/app/core/logging.py`
  - `src/app/main.py`
  - `src/app/temporal/worker.py`
  - All files with print() statements
- **Related Components**: All application components
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- Python logging: https://docs.python.org/3/library/logging.html

## Acceptance Criteria
- [ ] Centralized logging configuration created
- [ ] All print() statements replaced with logger calls
- [ ] Appropriate log levels used (info, warning, error)
- [ ] Log format includes timestamp, level, module
- [ ] Debug logging configurable via environment
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P3 NICE-TO-HAVE
- Estimated effort: Small (2 hours)

**Learnings:**
- Structured logging essential for production monitoring
- Consider JSON format for log aggregation systems

## Notes
Source: Triage session on 2025-12-04
