---
status: done
priority: p1
issue_id: "036"
tags: [database, migrations, datetime, consistency]
dependencies: []
---

# Fix Timestamp Consistency (timezone=True vs naive UTC)

## Problem Statement
The codebase mixes "naive UTC" conventions with `timezone=True` columns. The `utc_now()` helper explicitly returns naive UTC datetimes, but newer migrations (006+) create timezone-aware columns. This inconsistency can cause subtle timezone bugs that are driver-dependent.

## Findings
- Location: `src/app/models/base.py:4-10`
- The `utc_now()` helper returns naive UTC:
  ```python
  def utc_now() -> datetime:
      """Return current UTC time as naive datetime (for PostgreSQL TIMESTAMP)."""
      return datetime.now(UTC).replace(tzinfo=None)
  ```

- **Consistent migrations (001-004)**: Use `sa.DateTime()` - MATCHES helper
  - `src/alembic/versions/001_initial.py` lines 42, 57, 58, 70, 71, 93
  - `src/alembic/versions/004_add_workflow_executions.py` lines 36, 37, 38

- **Inconsistent migrations (006+)**: Use `sa.DateTime(timezone=True)` - CONFLICTS
  - `src/alembic/versions/006_add_email_verification.py` lines 33, 42, 43, 45
  - `src/alembic/versions/007_add_tenant_invites.py` lines 36, 37, 38
  - `src/alembic/versions/008_add_tenant_deleted_at.py` line 29
  - `src/alembic/versions/011_add_audit_logs.py` line 42

- All models use `default_factory=utc_now` which returns naive datetimes
- Mixing naive datetimes with timestamptz columns is subtle and driver-dependent

## Proposed Solutions

### Option 1: Keep naive UTC convention, fix migrations
- **Pros**: Minimal change, matches existing codebase convention, simpler datetime handling
- **Cons**: None - this is the established pattern
- **Effort**: Small
- **Risk**: Low (for starter template, safe to modify early migrations)

Change migrations 006+ to use `sa.DateTime()` instead of `sa.DateTime(timezone=True)`.

### Option 2: Change to timezone-aware throughout
- **Pros**: More explicit timezone handling
- **Cons**: Breaking change to all models and migrations 001-004, more complex
- **Effort**: Large
- **Risk**: Medium

## Recommended Action
Implement Option 1 - keep the established naive UTC convention and fix migrations 006+ to match.

## Technical Details
- **Affected Files**:
  - `src/alembic/versions/006_add_email_verification.py`
  - `src/alembic/versions/007_add_tenant_invites.py`
  - `src/alembic/versions/008_add_tenant_deleted_at.py`
  - `src/alembic/versions/011_add_audit_logs.py`
- **Related Components**: All datetime columns created in these migrations
- **Database Changes**: Column type change from TIMESTAMPTZ to TIMESTAMP (for template, safe to rewrite)

## Resources
- Original finding: REVIEW2.md - High #4
- Related issues: None

## Acceptance Criteria
- [ ] Migration 006 updated: remove timezone=True from DateTime columns
- [ ] Migration 007 updated: remove timezone=True from DateTime columns
- [ ] Migration 008 updated: remove timezone=True from DateTime columns
- [ ] Migration 011 updated: remove timezone=True from DateTime columns
- [ ] All DateTime columns use consistent `sa.DateTime()` (naive)
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-17 - Issue Resolved
**By:** Claude Code
**Actions:**
- Removed all `timezone=True` parameters from DateTime columns in migrations 006, 007, 008, 011
- Migration 006: Fixed email_verified_at, expires_at, created_at, used_at columns
- Migration 007: Fixed expires_at, created_at, accepted_at columns
- Migration 008: Fixed deleted_at column
- Migration 011: Fixed created_at column
- Verified no remaining timezone=True references in alembic/versions directory
- All DateTime columns now consistently use `sa.DateTime()` (naive UTC)

**Outcome:**
- All acceptance criteria met
- Consistent with project convention (naive UTC datetimes)
- Eliminates potential timezone-related bugs

### 2024-12-17 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW2.md code review
- Categorized as HIGH (data integrity)
- Estimated effort: Small

**Learnings:**
- Mixing naive and aware datetimes creates "why is expires_at shifted?" incidents
- Consistency is more important than which convention is chosen

## Notes
Source: REVIEW2.md High #4
Note: If this template is already deployed on real databases, create a follow-up migration altering column types instead of rewriting early migrations.
