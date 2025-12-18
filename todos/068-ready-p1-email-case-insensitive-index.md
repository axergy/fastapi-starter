---
status: ready
priority: p1
issue_id: "068"
tags: [data-integrity, database, index, auth, race-condition]
dependencies: []
---

# Race Condition in Email Registration (Case Sensitivity)

## Problem Statement
Email normalization to lowercase happens in the service layer, but the unique constraint is on the original email field. Two concurrent requests with different cases of the same email could both pass or one could fail unpredictably.

## Findings
- Location: `src/app/services/registration_service.py:56-78`
- Email is normalized with `email.lower().strip()` in service layer
- Database unique constraint doesn't account for case
- Concurrent registrations with same email (different case) can race
- PostgreSQL default string comparison is case-sensitive

## Proposed Solutions

### Option 1: Add functional index on LOWER(email)
- **Pros**: Database-enforced uniqueness, handles all edge cases
- **Cons**: Requires migration
- **Effort**: Small
- **Risk**: Low

```python
def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX ix_users_email_lower ON public.users (LOWER(email))"
    )

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_users_email_lower")
```

### Option 2: Use CITEXT column type
- **Pros**: Native case-insensitive comparison
- **Cons**: Requires column type change, more invasive
- **Effort**: Medium
- **Risk**: Medium

## Recommended Action
Add functional index on `LOWER(email)` - simpler and lower risk than changing column type.

## Technical Details
- **Affected Files**: New migration file in `src/alembic/versions/`
- **Related Components**: User registration, auth service
- **Database Changes**: Yes - adds functional unique index

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Migration created with functional index on LOWER(email)
- [ ] Concurrent registration with same email (different case) properly rejected
- [ ] Existing data validated for duplicates before migration
- [ ] Migration tested (upgrade and downgrade)
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
- Application-level normalization is not sufficient for uniqueness
- Database constraints are the last line of defense against race conditions

## Notes
Source: Triage session on 2025-12-18
