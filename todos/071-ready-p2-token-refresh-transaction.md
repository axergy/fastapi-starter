---
status: ready
priority: p2
issue_id: "071"
tags: [data-integrity, transaction, auth, security]
dependencies: []
---

# Missing Transaction for Token Refresh

## Problem Statement
The token refresh uses `FOR UPDATE` lock but doesn't wrap the operation in an explicit transaction. The `FOR UPDATE` lock is only effective within an explicit transaction context.

## Findings
- Location: `src/app/services/auth_service.py:172-202`
- Uses `FOR UPDATE` to lock token row
- No explicit `async with session.begin():` wrapper
- SQLAlchemy auto-starts transaction but lock behavior may be inconsistent
- Concurrent refresh requests could race

## Proposed Solutions

### Option 1: Wrap in explicit transaction
- **Pros**: Guarantees lock is held correctly, clear intent
- **Cons**: Minor code change
- **Effort**: Small
- **Risk**: Low

```python
async def refresh_tokens(self, refresh_token: str) -> TokenPair:
    async with self.session.begin():
        db_token = await self.token_repo.get_valid_by_hash_and_tenant(
            token_hash, self.tenant_id, for_update=True
        )
        if not db_token:
            raise ValueError("Invalid or expired refresh token")

        # Revoke old token
        db_token.revoked = True

        # Create new tokens
        # ... rest of logic
```

## Recommended Action
Wrap token refresh operations in explicit transaction block to ensure FOR UPDATE lock is properly held.

## Technical Details
- **Affected Files**: `src/app/services/auth_service.py`
- **Related Components**: Token repository, auth endpoints
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Token refresh wrapped in explicit transaction
- [ ] FOR UPDATE lock properly held during operation
- [ ] Concurrent refresh test added
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
- FOR UPDATE requires explicit transaction context for reliable locking
- SQLAlchemy's auto-transaction may not provide expected guarantees

## Notes
Source: Triage session on 2025-12-18
