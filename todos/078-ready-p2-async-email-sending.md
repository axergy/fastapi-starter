---
status: ready
priority: p2
issue_id: "078"
tags: [performance, async, email, blocking-io]
dependencies: []
---

# Email Sending Blocks Request Thread

## Problem Statement
Email sending appears to be synchronous. If `send_invite_email` makes a synchronous HTTP call to Resend API, it blocks the entire request. With a 10-second timeout, this significantly degrades user experience.

## Findings
- Location: `src/app/services/invite_service.py:107-112`
- `send_invite_email()` called synchronously
- HTTP call to external API (Resend)
- Blocks request thread for duration of API call
- Timeout configured at 10 seconds
- User must wait for email API response

## Proposed Solutions

### Option 1: Use FastAPI background tasks
- **Pros**: Simple, built-in, non-blocking
- **Cons**: No retry on failure, fire-and-forget
- **Effort**: Small
- **Risk**: Low

```python
from fastapi import BackgroundTasks

async def create_invite(
    self,
    email: str,
    invited_by_user_id: UUID,
    background_tasks: BackgroundTasks
) -> Invite:
    # ... create invite ...

    # Send email in background
    background_tasks.add_task(
        send_invite_email,
        to=email,
        token=token,
        tenant_name=tenant.name,
        inviter_name=inviter.full_name,
    )

    return invite
```

### Option 2: Make email sending fully async
- **Pros**: Non-blocking, can await if needed
- **Cons**: Requires async HTTP client
- **Effort**: Small
- **Risk**: Low

### Option 3: Offload to Temporal workflow
- **Pros**: Reliable delivery, automatic retries, audit trail
- **Cons**: More complex, requires workflow definition
- **Effort**: Medium
- **Risk**: Low

## Recommended Action
Use FastAPI background tasks for simplicity, or Temporal workflow for reliability if email delivery is critical.

## Technical Details
- **Affected Files**: `src/app/services/invite_service.py`, `src/app/core/email.py`
- **Related Components**: Invite endpoints, email service
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Email sending doesn't block request thread
- [ ] User receives immediate response after invite creation
- [ ] Email still sent reliably
- [ ] Error handling for failed sends
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
- External API calls should never block user-facing requests
- Background tasks are simple solution for fire-and-forget operations

## Notes
Source: Triage session on 2025-12-18
