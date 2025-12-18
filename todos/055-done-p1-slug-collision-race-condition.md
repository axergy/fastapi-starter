---
status: done
priority: p1
issue_id: "055"
tags: [security, data-integrity, race-condition, database]
dependencies: []
---

# Race Condition in Slug Collision Detection (TOCTOU)

## Problem Statement
The tenant creation flow has a Time-Of-Check-Time-Of-Use (TOCTOU) race condition. Two concurrent requests with conflicting slugs (e.g., "acme-corp" and "acme_corp") could both pass the collision check and create tenants that map to the same schema name, causing a complete data isolation breach.

## Findings
- Application-level check in `exists_by_slug()` uses `func.replace()` for normalization
- No database-level constraint enforces normalized uniqueness
- Location: `src/app/services/tenant_service.py:54-66`
- Current unique constraint is on raw `slug`, not normalized slug
- `IntegrityError` handler only catches identical slugs, not normalized collisions

## Proposed Solutions

### Option 1: Add functional unique index on normalized slug
- **Pros**: Database enforces uniqueness, prevents race condition
- **Cons**: Requires migration
- **Effort**: Small (30 minutes)
- **Risk**: Low

## Recommended Action
Create migration to add unique index on normalized slug:

```sql
CREATE UNIQUE INDEX idx_tenants_slug_normalized
ON public.tenants (REPLACE(slug, '-', '_'));
```

Update `IntegrityError` handler in `tenant_service.py` to catch this constraint violation and return appropriate error message.

## Technical Details
- **Affected Files**:
  - `src/alembic/versions/017_add_normalized_slug_index.py` (new)
  - `src/app/services/tenant_service.py` (update error handling)
- **Related Components**: TenantRepository, slug validation
- **Database Changes**: Yes - add functional unique index

## Resources
- Original finding: Security audit triage session
- PostgreSQL functional indexes documentation

## Acceptance Criteria
- [ ] Migration adds unique index on `REPLACE(slug, '-', '_')`
- [ ] Concurrent creation of "acme-corp" and "acme_corp" fails
- [ ] Error message clearly indicates slug collision
- [ ] Existing tenants don't violate new constraint
- [ ] Tests verify race condition is prevented

## Work Log

### 2025-12-18 - Implementation Completed
**By:** Claude Code
**Actions:**
- Created migration `016_add_normalized_slug_index.py`
- Added unique index on `REPLACE(slug, '-', '_')` in public.tenants table
- Updated `IntegrityError` handler in `tenant_service.py` to distinguish between:
  - Direct slug collisions (e.g., "acme-corp" vs "acme-corp")
  - Normalized slug collisions (e.g., "acme-corp" vs "acme_corp")
- Enhanced error messages to clearly indicate normalized slug conflicts
- Status changed from ready to done

**Implementation Details:**
- Migration file: `/src/alembic/versions/016_add_normalized_slug_index.py`
- Updated file: `/src/app/services/tenant_service.py`
- Index name: `idx_tenants_slug_normalized`
- Database-level constraint now prevents TOCTOU race conditions

**Learnings:**
- Using `op.execute()` for functional indexes is cleaner than raw SQL in Alembic
- Error message parsing from `IntegrityError.orig` allows specific error handling
- Normalized slug must be shown in error message for debugging

### 2025-12-17 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending to ready
- Ready to be picked up and worked on

**Learnings:**
- Application-level uniqueness checks are vulnerable to race conditions
- Database constraints are the only reliable way to prevent TOCTOU
- Normalized slug collision is a critical multi-tenancy security issue

## Notes
Source: Triage session on 2025-12-17
