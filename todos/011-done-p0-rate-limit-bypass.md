---
id: "011"
title: "Rate-Limit Bypass via X-Tenant-ID"
status: pending
priority: p0
source: "REVIEW.md - CRITICAL #2"
category: security
---

# Rate-Limit Bypass via X-Tenant-ID

## Problem

`get_rate_limit_key()` includes the attacker-controlled `X-Tenant-ID` header in the rate limit bucket key. An attacker can trivially bypass rate limiting by rotating the X-Tenant-ID value on each request, creating a new bucket each time.

## Risk

- **DoS attack enablement**: Rate limiting becomes completely ineffective
- **Memory exhaustion**: Unbounded growth of `_rate_limit_buckets` dictionary
- **Resource abuse**: Attackers can make unlimited requests

## Verified Findings

| Location | Line | Issue |
|----------|------|-------|
| `src/app/core/rate_limit.py` | 69 | `tenant_id = request.headers.get("X-Tenant-ID", "")` |
| `src/app/core/rate_limit.py` | 71 | `return f"{ip}:{tenant_id}"` - tenant_id in key |

### Attack Scenario

```bash
# Each request gets a new rate limit bucket
curl -H "X-Tenant-ID: random1" /api/endpoint
curl -H "X-Tenant-ID: random2" /api/endpoint
curl -H "X-Tenant-ID: random3" /api/endpoint
# ... unlimited requests bypass rate limiting
```

## Fix

Remove tenant_id from rate limit key - use IP only for unauthenticated requests, or IP + authenticated user_id for authenticated requests.

### Code Changes

**src/app/core/rate_limit.py:**
```python
def get_rate_limit_key(request: Request) -> str:
    """Generate rate limit key from client IP only.

    WARNING: Do NOT include user-controlled headers (like X-Tenant-ID)
    as this allows trivial rate limit bypass by rotating header values.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    return ip  # IP only, no tenant_id
```

## Files to Modify

- `src/app/core/rate_limit.py`
- `tests/unit/test_rate_limit.py` (update tests expecting ip:tenant format)

## Acceptance Criteria

- [ ] Rate limit key uses IP only, not X-Tenant-ID header
- [ ] Tests updated to expect IP-only keys
- [ ] Security comment added explaining why tenant_id excluded
- [ ] Consider adding authenticated user_id for logged-in rate limiting (separate bucket)
