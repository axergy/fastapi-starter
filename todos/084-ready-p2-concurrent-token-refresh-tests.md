---
status: ready
priority: p2
issue_id: "084"
tags: [testing, security, concurrency, auth]
dependencies: ["071"]
---

# Missing Integration Tests for Concurrent Token Refresh

## Problem Statement
The `FOR UPDATE` lock in token refresh needs testing with concurrent requests to verify it prevents double-token-issuance race conditions.

## Findings
- Location: Tests directory - missing test
- Token refresh uses FOR UPDATE lock
- No concurrent access tests exist
- Race condition prevention unverified
- Security guarantee untested

## Proposed Solutions

### Option 1: Add concurrent token refresh test
- **Pros**: Verifies critical security behavior, catches regressions
- **Cons**: Requires async test setup
- **Effort**: Small
- **Risk**: Low

```python
import asyncio
import pytest
from httpx import AsyncClient

@pytest.mark.integration
async def test_concurrent_token_refresh_prevents_double_issue(
    async_client: AsyncClient,
    authenticated_user_tokens: dict,
):
    """Test that concurrent refresh requests don't issue duplicate tokens."""
    refresh_token = authenticated_user_tokens["refresh_token"]

    # Launch 10 concurrent refresh requests
    async def refresh():
        return await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

    results = await asyncio.gather(
        *[refresh() for _ in range(10)],
        return_exceptions=True
    )

    # Exactly one should succeed
    successes = [r for r in results if hasattr(r, 'status_code') and r.status_code == 200]
    failures = [r for r in results if hasattr(r, 'status_code') and r.status_code in (400, 401)]

    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
    assert len(failures) == 9, f"Expected 9 failures, got {len(failures)}"

    # Verify the successful response has new tokens
    success_data = successes[0].json()
    assert "access_token" in success_data
    assert "refresh_token" in success_data
```

## Recommended Action
Add integration test for concurrent token refresh to verify FOR UPDATE lock behavior.

## Technical Details
- **Affected Files**: `tests/integration/test_auth.py`
- **Related Components**: Auth service, token repository
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- Related todo: #071 (token refresh transaction)

## Acceptance Criteria
- [ ] Concurrent token refresh test implemented
- [ ] Test verifies exactly one request succeeds
- [ ] Test verifies other requests fail gracefully
- [ ] Test runs reliably (no flakiness)
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Security-critical code paths need explicit testing
- Concurrent tests catch race conditions that unit tests miss

## Notes
Source: Triage session on 2025-12-18
