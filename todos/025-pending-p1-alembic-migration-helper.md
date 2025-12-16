---
status: pending
priority: p1
issue_id: "025"
tags: [migration, dry, foundation]
dependencies: []
---

# Add Shared Alembic Migration Helper

## Problem Statement
12 migrations repeat `if context.get_tag_argument(): return` pattern (24 occurrences total in upgrade/downgrade). Each migration imports `context` solely for this check. This is a DRY violation that should be centralized.

## Findings
- Pattern found in migrations 003-014 (both upgrade and downgrade functions)
- `src/alembic/migration_utils.py` does NOT exist
- Example from 003_add_performance_indexes.py lines 22-23:
  ```python
  if context.get_tag_argument():
      return
  ```
- Each migration has similar comments explaining the pattern
- Total: 24 instances across 12 migration files

## Proposed Solutions

### Option 1: Create migration_utils.py with is_tenant_migration() helper
- **Pros**: Single source of truth, cleaner migrations, removes 24 duplicate code blocks
- **Cons**: None significant
- **Effort**: Medium (create helper + update 12 files)
- **Risk**: Low

## Recommended Action
Create `src/alembic/migration_utils.py` with helper function, then apply to all migrations.

## Technical Details
- **Affected Files**:
  - New: `src/alembic/migration_utils.py`
  - Edit: `src/alembic/versions/001_initial.py` (after Issue 024)
  - Edit: `src/alembic/versions/003_*.py` through `014_*.py` (12 files)
- **Related Components**: All public schema migrations
- **Database Changes**: No

## Resources
- Original finding: REVIEW.md - High #4
- Related issues: #024 (depends on this)

## Acceptance Criteria
- [ ] `src/alembic/migration_utils.py` created with `is_tenant_migration()` function
- [ ] All 12 migrations (003-014) updated to use helper
- [ ] `from alembic import context` removed from each migration
- [ ] `from src.alembic.migration_utils import is_tenant_migration` added
- [ ] Duplicate comments removed or simplified
- [ ] Tests pass

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P1 (DRY foundation)
- Estimated effort: Medium
- Foundation for Issue 024

**Learnings:**
- This is a foundational change that enables cleaner migrations

## Notes
Source: REVIEW.md Round 3 - Code Cleanup

Helper implementation:
```python
from __future__ import annotations

from alembic import context


def is_tenant_migration() -> bool:
    """True when Alembic was invoked with `--tag=<tenant_schema>`.

    In this codebase, tags are used to indicate tenant-schema migrations.
    Public-schema migrations must no-op in that mode.
    """
    return bool(context.get_tag_argument())
```
