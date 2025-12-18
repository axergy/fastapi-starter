---
status: ready
priority: p2
issue_id: "076"
tags: [performance, database, n+1, query-optimization]
dependencies: []
---

# N+1 Query in Invite Creation

## Problem Statement
After committing invite, tenant and inviter are fetched separately with two additional queries. This could be optimized with a single query using joins.

## Findings
- Location: `src/app/services/invite_service.py:102-104`
- Current flow: INSERT invite → SELECT tenant → SELECT user
- 3 round trips to database
- Tenant and inviter IDs known upfront
- Could be fetched in single query

## Proposed Solutions

### Option 1: Fetch tenant and inviter in single joined query
- **Pros**: Reduces queries from 3 to 2, simpler DB load
- **Cons**: Minor code refactor
- **Effort**: Small
- **Risk**: Low

```python
async def create_invite(self, email: str, invited_by_user_id: UUID) -> Invite:
    # Fetch tenant and inviter in one query before creating invite
    query = select(Tenant, User).where(
        Tenant.id == self.tenant_id,
        User.id == invited_by_user_id
    )
    result = await self.session.execute(query)
    row = result.one_or_none()

    if not row:
        raise ValueError("Tenant or inviter not found")

    tenant, inviter = row

    # Now create invite with data already loaded
    invite = Invite(
        email=email.lower().strip(),
        tenant_id=self.tenant_id,
        invited_by_user_id=invited_by_user_id,
        token=secrets.token_urlsafe(32),
        expires_at=utc_now() + timedelta(days=7),
    )
    self.invite_repo.add(invite)
    await self.session.commit()
    await self.session.refresh(invite)

    # Use already-loaded tenant and inviter for email
    send_invite_email(
        to=email,
        token=invite.token,
        tenant_name=tenant.name,
        inviter_name=inviter.full_name,
    )

    return invite
```

## Recommended Action
Refactor to fetch tenant and inviter in single query before creating invite.

## Technical Details
- **Affected Files**: `src/app/services/invite_service.py`
- **Related Components**: Invite creation flow
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Tenant and inviter fetched in single query
- [ ] Total queries reduced from 3 to 2
- [ ] Existing functionality preserved
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
- N+1 queries add up quickly in high-traffic endpoints
- Prefetch related data when IDs are known upfront

## Notes
Source: Triage session on 2025-12-18
