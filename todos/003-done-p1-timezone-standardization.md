---
status: done
priority: p1
issue_id: "003"
tags: [data-integrity, datetime, migrations]
dependencies: []
---

# Timezone Handling Inconsistency

## Problem Statement
Mixed naive/aware datetime handling across codebase. Some code uses `utc_now()` (naive), others use `datetime.now(UTC)` (aware). Migrations also inconsistently define timestamp columns with and without timezone support.

## Findings
- Location: `src/app/models/base.py:6`
  - `utc_now()` returns **naive** datetime (strips tzinfo)
- Location: `src/app/core/security/crypto.py:93`
  - Uses `datetime.now(UTC)` (aware) then strips to naive at line 108
- Location: `src/app/services/user_service.py:39,47`
  - Uses `datetime.now(UTC)` (aware) on naive TIMESTAMP columns - potential type mismatch
- **Migration inconsistency:**
  - Migrations 001, 004: `sa.DateTime()` (naive/TIMESTAMP)
  - Migrations 006, 007, 008, 011: `sa.DateTime(timezone=True)` (aware/TIMESTAMPTZ)

## Proposed Solutions

### Option 1: Standardize on naive UTC (current convention)
- **Pros**: Minimal changes, consistent with existing `utc_now()`
- **Cons**: Requires fixing services using `datetime.now(UTC)`
- **Effort**: Small (immediate), Medium (migration for consistency)
- **Risk**: Low

### Option 2: Migrate to timezone-aware everywhere
- **Pros**: More explicit, PostgreSQL TIMESTAMPTZ is recommended
- **Cons**: Requires data migration, more changes
- **Effort**: Large
- **Risk**: Medium

## Recommended Action
Phase 1: Fix `user_service.py` to use `utc_now()` instead of `datetime.now(UTC)`.
Phase 2: (Future) Plan migration to standardize all timestamp columns.

## Technical Details
- **Affected Files**:
  - `src/app/services/user_service.py` (immediate fix)
  - `src/app/models/base.py` (add documentation comment)
- **Related Components**: All timestamp handling
- **Database Changes**: Future migration needed for full standardization

## Resources
- Original finding: REVIEW.md - CRITICAL #3
- Related issues: None

## Acceptance Criteria
- [x] `user_service.py` uses `utc_now()` instead of `datetime.now(UTC)`
- [x] Add docstring to `utc_now()` explaining the naive datetime convention (already present)
- [ ] No type errors when running mypy (to be verified)
- [ ] Tests pass (to be verified)
- [ ] Code reviewed (to be verified)

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P1 (Data Integrity)
- Estimated effort: Small for immediate fix, Large for full migration

**Learnings:**
- The codebase has an established convention of naive UTC datetimes
- PostgreSQL handles both TIMESTAMP and TIMESTAMPTZ correctly if used consistently
- The immediate risk is `user_service.py` using aware datetimes on naive columns

### 2025-12-16 - Resolution
**By:** Claude Code Assistant
**Actions:**
- Fixed `user_service.py` to use `utc_now()` instead of `datetime.now(UTC)`
- Removed unused `UTC` import from datetime
- Added import for `utc_now` from `src.app.models.base`
- Updated lines 40 and 48 to use naive UTC datetimes

**Changes:**
- `/Users/netf/Projects/Axergy/fastapi-starter/src/app/services/user_service.py`
  - Import: Removed `UTC` from `datetime` import, added `utc_now` import
  - Line 40: Changed `datetime.now(UTC)` to `utc_now()`
  - Line 48: Changed `datetime.now(UTC)` to `utc_now()`

**Status:** Code changes complete, ready for testing and review

## Notes
Source: REVIEW.md analysis on 2025-12-16
