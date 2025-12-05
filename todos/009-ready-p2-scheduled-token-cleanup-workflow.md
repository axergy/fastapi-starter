---
status: ready
priority: p2
issue_id: "009"
tags: [security, database, temporal, scheduled-workflow, token-management]
dependencies: []
---

# Expired Tokens Never Cleaned Up - Implement Scheduled Temporal Cleanup

## Problem Statement
Expired tokens (email verification, refresh tokens, invites) remain in the database forever. The tables grow unbounded, causing performance degradation, increased storage costs, and security hygiene concerns. Need to implement a Temporal scheduled workflow for cleanup with configurable cron-like syntax.

## Findings
- Location: Multiple repositories (no cleanup methods exist)
- No mechanism to delete expired/used tokens
- Tables grow indefinitely over time
- Potential performance impact on token validation queries

**Tables Requiring Cleanup:**
| Table | Cleanup Criteria |
|-------|-----------------|
| `email_verification_tokens` | `expires_at < now() - retention` OR `used = true AND used_at < now() - retention` |
| `refresh_tokens` | `expires_at < now() - retention` OR `revoked = true AND updated_at < now() - retention` |
| `tenant_invites` | `expires_at < now() - retention` OR `accepted_at IS NOT NULL AND accepted_at < now() - retention` |

## Proposed Solutions

### Option 1: Temporal Scheduled Workflow with Configurable Cron
- Add `cleanup_schedule` config setting (cron syntax)
- Add `cleanup_retention_days` config setting
- Create `TokenCleanupWorkflow` Temporal workflow
- Add cleanup activities for each token type
- Schedule workflow on app startup
- Log cleanup stats for monitoring
- **Pros**: Reliable, observable, uses existing Temporal infrastructure
- **Cons**: Requires Temporal to be running
- **Effort**: Medium (3-4 hours)
- **Risk**: Low

**Example Config:**
```python
# config.py
cleanup_schedule: str | None = "0 3 * * *"  # Daily at 3am UTC, None to disable
cleanup_retention_days: int = 30
```

**Workflow Structure:**
```python
@workflow.defn
class TokenCleanupWorkflow:
    @workflow.run
    async def run(self) -> CleanupResult:
        email_tokens = await workflow.execute_activity(
            cleanup_email_verification_tokens,
            start_to_close_timeout=timedelta(minutes=5),
        )
        refresh_tokens = await workflow.execute_activity(
            cleanup_refresh_tokens,
            start_to_close_timeout=timedelta(minutes=5),
        )
        invites = await workflow.execute_activity(
            cleanup_expired_invites,
            start_to_close_timeout=timedelta(minutes=5),
        )
        return CleanupResult(
            email_tokens_deleted=email_tokens,
            refresh_tokens_deleted=refresh_tokens,
            invites_deleted=invites,
        )
```

**Schedule Creation:**
```python
await client.create_schedule(
    "token-cleanup-schedule",
    Schedule(
        action=ScheduleActionStartWorkflow(
            TokenCleanupWorkflow.run,
            id="token-cleanup",
            task_queue="main-task-queue",
        ),
        spec=ScheduleSpec(cron_expressions=[settings.cleanup_schedule]),
    ),
)
```

## Recommended Action
Implement Temporal scheduled workflow with configurable cron and retention settings

## Technical Details
- **Affected Files**:
  - `src/app/core/config.py` - Add cleanup settings
  - `src/app/temporal/workflows.py` - Add TokenCleanupWorkflow
  - `src/app/temporal/activities.py` - Add cleanup activities
  - `src/app/repositories/public/email_verification.py` - Add cleanup method
  - `src/app/repositories/public/token.py` - Add cleanup method
  - `src/app/repositories/public/invite.py` - Add cleanup method
  - `src/app/main.py` or startup script - Schedule creation
- **Related Components**: Temporal, all token repositories
- **Database Changes**: No schema changes, just DELETE operations

## Resources
- Original finding: Code review triage session
- Temporal Schedules: https://docs.temporal.io/workflows#schedule
- Cron syntax reference: https://crontab.guru/

## Acceptance Criteria
- [ ] `cleanup_schedule` config setting added (cron syntax, nullable to disable)
- [ ] `cleanup_retention_days` config setting added (default 30)
- [ ] `TokenCleanupWorkflow` implemented with activities for each token type
- [ ] Schedule created on app startup (if cleanup_schedule configured)
- [ ] Cleanup activities are idempotent
- [ ] Cleanup stats logged for monitoring
- [ ] Tests verify cleanup deletes correct records
- [ ] Documentation for configuration

## Work Log

### 2025-12-05 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage session
- Categorized as P2 IMPORTANT (Security/Database Hygiene)
- Estimated effort: Medium (3-4 hours)
- Solution: Temporal scheduled workflow with cron config

**Learnings:**
- Token tables grow unbounded without cleanup
- Temporal schedules provide reliable, observable cleanup mechanism
- Cron syntax allows flexible scheduling configuration

## Notes
Source: Triage session on 2025-12-05
Related to Issue #005 (RefreshToken index) - cleanup reduces table size, improving index efficiency.
