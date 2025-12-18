---
status: ready
priority: p2
issue_id: "072"
tags: [error-handling, redis, security, cache]
dependencies: []
---

# Redis Pipeline Error Handling - Silent Failures

## Problem Statement
Redis pipeline execution doesn't check for partial failures. If some commands in the pipeline fail, we still return the full count. The caller has no way to know if blacklisting was partial.

## Findings
- Location: `src/app/core/cache.py:62-64`
- Pipeline executes multiple SETEX commands
- Returns `len(token_hashes)` regardless of actual success
- No inspection of pipeline results
- Partial failures silently ignored

## Proposed Solutions

### Option 1: Check pipeline results and return actual count
- **Pros**: Accurate reporting, caller can handle partial failures
- **Cons**: Minor code change
- **Effort**: Small
- **Risk**: Low

```python
async def blacklist_tokens(token_hashes: list[str], ttl: int) -> int:
    """Blacklist multiple tokens. Returns actual number blacklisted."""
    redis = await get_redis()
    if not redis or not token_hashes:
        return 0

    pipe = redis.pipeline()
    for token_hash in token_hashes:
        pipe.setex(f"{PREFIX_TOKEN_BLACKLIST}:{token_hash}", ttl, "1")

    results = await pipe.execute()
    successful = sum(1 for r in results if r)

    if successful < len(token_hashes):
        logger.warning(
            f"Partial token blacklist: {successful}/{len(token_hashes)} succeeded"
        )

    return successful
```

## Recommended Action
Inspect pipeline results and return actual success count, with warning log for partial failures.

## Technical Details
- **Affected Files**: `src/app/core/cache.py`
- **Related Components**: Auth service, token blacklisting
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Pipeline results inspected for success/failure
- [ ] Return actual success count
- [ ] Log warning on partial failures
- [ ] Tests for partial failure scenarios
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Redis pipelines can have partial failures
- Always inspect pipeline results for accurate error handling

## Notes
Source: Triage session on 2025-12-18
