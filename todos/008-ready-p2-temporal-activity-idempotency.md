---
status: resolved
priority: p2
issue_id: "008"
tags: [data-integrity, temporal, idempotency, workflows]
dependencies: []
---

# Temporal Workflows/Activities Missing Idempotency Guarantees

## Problem Statement
Temporal activities that perform external calls or side effects need idempotency guarantees. If Temporal retries an activity after a network failure or worker crash, non-idempotent operations could execute multiple times, causing data inconsistencies, duplicate records, or duplicate external API calls.

## Findings
- Location: `src/app/temporal/activities.py` (all activities)
- Temporal automatically retries failed activities
- Network failures can cause "successful" activities to be retried
- Not all activities have idempotency guarantees

**Problem Scenario:**
1. Temporal starts an activity (e.g., send email, create schema, update record)
2. Activity completes successfully
3. Network failure before Temporal receives acknowledgment
4. Temporal retries activity (as per retry policy)
5. Operation executes twice - duplicate email sent, inconsistent state, etc.

**Activities to Audit:**
| Activity | Current State | Risk |
|----------|--------------|------|
| `create_tenant_schema` | Uses raw SQL | Medium - could fail if schema exists |
| `run_migrations` | Alembic migrations | Low - Alembic tracks state |
| `send_welcome_email` | Sends email | High - could send duplicates |
| `drop_tenant_schema` | Has `IF EXISTS` | Low - already idempotent ✓ |
| `soft_delete_tenant` | Updates record | Medium - needs idempotency check |
| Future external APIs | N/A | High - need idempotency keys |

## Proposed Solutions

### Option 1: Comprehensive Idempotency Audit & Fix
- Audit all activities for idempotency guarantees
- Add `IF NOT EXISTS` / `IF EXISTS` for SQL DDL operations
- Implement "check-then-act" patterns with proper guards
- Add idempotency tracking table for external calls
- Document idempotency guarantees for each activity
- **Pros**: Complete solution, prevents all retry-related issues
- **Cons**: Requires careful audit of each activity
- **Effort**: Medium (2-4 hours)
- **Risk**: Low

**Implementation Patterns:**
```python
# Pattern 1: SQL with IF NOT EXISTS
await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))

# Pattern 2: Check-then-act with guard
existing = await repo.get_by_id(id)
if existing and existing.processed:
    return existing  # Already done, return cached result

# Pattern 3: Idempotency key tracking
async def send_email_idempotent(idempotency_key: str, ...):
    if await idempotency_store.exists(idempotency_key):
        return  # Already sent
    await send_email(...)
    await idempotency_store.mark_complete(idempotency_key)
```

## Recommended Action
Audit all activities and implement appropriate idempotency patterns for each

## Technical Details
- **Affected Files**:
  - `src/app/temporal/activities.py`
  - `src/app/temporal/workflows.py`
  - Potentially new idempotency tracking table/service
- **Related Components**: All Temporal workflows, external integrations
- **Database Changes**: Possibly - idempotency tracking table

## Resources
- Original finding: Code review triage session
- Temporal Idempotency: https://docs.temporal.io/activities#idempotency
- Temporal Best Practices: https://docs.temporal.io/dev-guide/python/foundations#activity-definition

## Acceptance Criteria
- [ ] All activities audited for idempotency
- [ ] SQL DDL operations use IF EXISTS/IF NOT EXISTS
- [ ] Email sending has duplicate prevention
- [ ] External API calls have idempotency key pattern documented
- [ ] Each activity has documented idempotency guarantee
- [ ] Tests verify idempotency (retry same activity, expect same result)

## Work Log

### 2025-12-05 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage session
- Categorized as P2 IMPORTANT (Data Integrity)
- Estimated effort: Medium (2-4 hours)
- Scope expanded from Stripe-specific to all activities

**Learnings:**
- Temporal retries require all activities to be idempotent
- Network failures can cause "successful" operations to retry
- Different patterns needed for different operation types

## Notes
Source: Triage session on 2025-12-05
Important foundation for adding any external integrations (Stripe, etc.) in the future.
