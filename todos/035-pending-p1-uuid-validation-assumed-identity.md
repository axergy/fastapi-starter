---
status: done
priority: p1
issue_id: "035"
tags: [security, auth, validation, error-handling]
dependencies: []
---

# Fix UUID Validation in Assumed Identity Token

## Problem Statement
The `_validate_access_token()` function can raise a 500 Internal Server Error when an invalid tenant_id is provided in the assumed-identity JWT payload. Currently, the code directly converts `payload.get("tenant_id", "")` to UUID without proper error handling. Malformed tokens should return 401 Unauthorized, not expose internal exceptions.

## Findings
- Location: `src/app/api/dependencies/auth.py:135`
- Problematic code:
  ```python
  assumed_identity_ctx = AssumedIdentityContext(
      operator_user_id=operator_user_uuid,
      assumed_user_id=user_uuid,
      tenant_id=UUID(payload.get("tenant_id", "")),  # No try/except!
      reason=assumed_identity_data.get("reason"),
      started_at=started_at,
  )
  ```
- The code correctly handles `user_id` (line ~74) and `operator_user_id` (line ~104) with try/except blocks
- But `tenant_id` in the assumed identity context construction is NOT guarded
- When `payload.get("tenant_id", "")` returns an invalid UUID string or empty string, `UUID()` raises `ValueError`
- This causes a 500 error instead of proper 401 response

## Proposed Solutions

### Option 1: Wrap tenant_id conversion in try/except
- **Pros**: Consistent with existing pattern for other UUIDs, proper error response
- **Cons**: None
- **Effort**: Small
- **Risk**: Low

```python
try:
    token_tenant_id = UUID(str(payload.get("tenant_id", "")))
except (ValueError, TypeError):
    raise HTTPException(status_code=401, detail="Invalid token")

assumed_identity_ctx = AssumedIdentityContext(
    operator_user_id=operator_user_uuid,
    assumed_user_id=user_uuid,
    tenant_id=token_tenant_id,
    reason=assumed_identity_data.get("reason"),
    started_at=started_at,
)
```

## Recommended Action
Implement Option 1 - add proper try/except handling for tenant_id UUID conversion.

## Technical Details
- **Affected Files**: `src/app/api/dependencies/auth.py`
- **Related Components**: Authentication, assumed identity, JWT validation
- **Database Changes**: No

## Resources
- Original finding: REVIEW2.md - Critical #2
- Related issues: None

## Acceptance Criteria
- [ ] tenant_id UUID conversion wrapped in try/except
- [ ] Invalid tenant_id in token returns 401, not 500
- [ ] Also catch TypeError in addition to ValueError
- [ ] Tests added for malformed assumed identity tokens
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2024-12-17 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW2.md code review
- Categorized as CRITICAL
- Estimated effort: Small

**Learnings:**
- This is a "works in tests, surprises in prod" bug pattern
- All JWT payload field conversions should be guarded

## Notes
Source: REVIEW2.md Critical #2
