---
status: pending
priority: p1
issue_id: "023"
tags: [migration, cleanup, dead-code]
dependencies: []
---

# Delete Redundant Migration 002

## Problem Statement
Migration 002_add_tenant_status duplicates functionality from 001_initial. For fresh template installs, this migration is a no-op and confuses maintainers about the migration history.

## Findings
- `src/alembic/versions/001_initial.py` lines 39-44: Creates `tenants.status` column with server_default="provisioning"
- `src/alembic/versions/002_add_tenant_status.py` lines 7-9: Contains idempotent note explaining it conditionally adds the same column
- For fresh installs, 002 is completely redundant
- This is template cruft from historical evolution

## Proposed Solutions

### Option 1: Delete migration 002 and re-point 003
- **Pros**: Clean migration history, removes confusion
- **Cons**: Breaks existing databases that ran old 001 without status column
- **Effort**: Small
- **Risk**: Low (template is for new projects)

## Recommended Action
Delete 002 and update 003's down_revision to "001". This is ideal for a starter template targeting new databases.

## Technical Details
- **Affected Files**:
  - Delete: `src/alembic/versions/002_add_tenant_status.py`
  - Edit: `src/alembic/versions/003_add_performance_indexes.py` (change down_revision)
- **Related Components**: Alembic migration chain
- **Database Changes**: No schema changes (cleanup only)

## Resources
- Original finding: REVIEW.md - Critical #1
- Related issues: None

## Acceptance Criteria
- [ ] Migration 002 deleted
- [ ] Migration 003 has `down_revision = "001"`
- [ ] Header comment in 003 updated ("Revises: 001")
- [ ] `alembic history` shows clean chain: 001 -> 003 -> ...
- [ ] Tests pass

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P1 (template cleanup)
- Estimated effort: Small

**Learnings:**
- Migration 002 was a safety net for legacy databases but is noise in a clean template

## Notes
Source: REVIEW.md Round 3 - Code Cleanup
