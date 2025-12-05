---
status: ready
priority: p3
issue_id: "014"
tags: [observability, logging, structured-logging, debugging]
dependencies: []
---

# Missing Structured Logging Fields

## Problem Statement
Logging uses structured logging (structlog) but many log statements don't include contextual fields like `user_id`, `tenant_id`, `request_id`. This makes it harder to filter and correlate logs in production, significantly impacting debugging and monitoring capabilities.

## Findings
- Location: Multiple service files
- structlog is configured but context not bound consistently
- Log entries missing user_id, tenant_id, request_id
- Cannot filter logs by tenant or user in log aggregation tools
- Manual correlation required across log entries

**Problem Scenario:**
1. Error occurs in production
2. Log entry shows: `"User login failed"`
3. Missing context: Which user? Which tenant? Which request?
4. Cannot filter logs by user_id or tenant_id
5. Debugging requires manual correlation across log entries

**Current State:**
```python
logger.info("User login failed")
# Output: {"event": "User login failed", "timestamp": "..."}
```

**Desired State:**
```python
logger.info("User login failed")
# Output: {"event": "User login failed", "user_id": "...", "tenant_id": "...", "request_id": "...", "timestamp": "..."}
```

## Proposed Solutions

### Option 1: Request-Scoped Context with Middleware
- Use structlog contextvars to bind context at request start
- Middleware extracts user_id, tenant_id from auth
- All subsequent logs automatically include context
- **Pros**: Automatic, no changes to existing log calls
- **Cons**: Requires middleware setup
- **Effort**: Medium (2-3 hours)
- **Risk**: Low

**Implementation:**
```python
# src/app/core/logging.py
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

# Middleware
@app.middleware("http")
async def logging_context_middleware(request: Request, call_next):
    clear_contextvars()

    # Bind request_id from correlation middleware
    request_id = correlation_id.get()
    bind_contextvars(request_id=request_id)

    response = await call_next(request)
    return response

# In auth dependency, after user is resolved
def bind_user_context(user: User, tenant_id: UUID):
    bind_contextvars(
        user_id=str(user.id),
        tenant_id=str(tenant_id),
        user_email=user.email,
    )
```

**Usage (no changes needed to existing code):**
```python
# This automatically includes user_id, tenant_id, request_id
logger.info("User login successful")
logger.error("Payment failed", amount=100)
```

## Recommended Action
Implement request-scoped context binding via middleware and auth dependencies

## Technical Details
- **Affected Files**:
  - `src/app/core/logging.py` - Add context binding helpers
  - `src/app/main.py` - Add middleware
  - `src/app/api/dependencies/auth.py` - Bind user context after auth
- **Related Components**: All services that log, monitoring/alerting
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- structlog contextvars: https://www.structlog.org/en/stable/contextvars.html

## Acceptance Criteria
- [ ] Middleware binds request_id to log context
- [ ] Auth dependency binds user_id and tenant_id after authentication
- [ ] All log entries include context fields automatically
- [ ] Context cleared between requests (no leaking)
- [ ] Log aggregation can filter by user_id, tenant_id
- [ ] Tests verify context binding works correctly

## Work Log

### 2025-12-05 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage session
- Categorized as P3 NICE-TO-HAVE (Observability)
- Estimated effort: Medium (2-3 hours)

**Learnings:**
- structlog contextvars enable automatic context propagation
- Context should be bound as early as possible in request lifecycle

## Notes
Source: Triage session on 2025-12-05
Important for production debugging and monitoring.
