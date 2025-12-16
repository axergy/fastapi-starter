---
status: pending
priority: p1
issue_id: "024"
tags: [migration, cleanup, dead-code]
dependencies: ["025"]
---

# Remove Placeholder Blocks in Migration 001

## Problem Statement
001_initial has dead code with "Future tenant-specific tables go here" comments. This placeholder pattern is template cruft that confuses maintainers and should be replaced with a clean early-return pattern.

## Findings
- `src/alembic/versions/001_initial.py` lines 26-29: `if schema: pass` with "Future tenant-specific tables go here" comment
- Lines 119-123: Same pattern in downgrade() with "Tenant schema - nothing to drop" comment
- The code imports `context` but only uses it for the tenant check
- Pattern should use the `is_tenant_migration()` helper from migration_utils.py

## Proposed Solutions

### Option 1: Use early return with migration helper
- **Pros**: Clean, DRY, consistent with other migrations
- **Cons**: Requires migration_utils.py (Issue 025)
- **Effort**: Small
- **Risk**: Low

## Recommended Action
Replace the `if schema: pass else:` pattern with early return using `is_tenant_migration()` helper.

## Technical Details
- **Affected Files**:
  - `src/alembic/versions/001_initial.py`
- **Related Components**: Depends on Issue 025 (migration_utils.py)
- **Database Changes**: No

## Resources
- Original finding: REVIEW.md - Critical #2
- Related issues: #025 (migration helper)

## Acceptance Criteria
- [ ] `if schema: pass` blocks removed from upgrade() and downgrade()
- [ ] Early return pattern: `if is_tenant_migration(): return`
- [ ] Import changed from `context` to `is_tenant_migration`
- [ ] No "Future..." placeholder comments
- [ ] Tests pass

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P1 (dead code removal)
- Estimated effort: Small
- Depends on Issue 025

**Learnings:**
- Migration 001 is the foundation migration and should be the cleanest

## Notes
Source: REVIEW.md Round 3 - Code Cleanup
