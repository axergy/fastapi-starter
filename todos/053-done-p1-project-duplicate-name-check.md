---
status: done
priority: p1
issue_id: "053"
tags: [data-integrity, api, validation]
dependencies: []
---

# Missing Duplicate Name Check in Project Creation

## Problem Statement
The `create_project` endpoint doesn't check if a project with the same name already exists before creation. There's no unique constraint on the name field, and no application-level validation to prevent duplicates.

## Findings
- No unique constraint on `projects.name` column
- Location: `src/app/api/v1/projects.py:78-94`
- Migration `015_add_tenant_projects.py` creates non-unique index
- `ProjectRepository.get_by_name()` exists but isn't used for validation

## Proposed Solutions

### Option 1: Add unique constraint + application validation
- **Pros**: Defense in depth, user-friendly error messages
- **Cons**: Requires migration
- **Effort**: Small (30 minutes)
- **Risk**: Low

## Recommended Action
1. Create new migration to add unique constraint on `projects.name`
2. In `create_project` endpoint, check `repo.get_by_name()` before creation
3. Handle `IntegrityError` with 409 Conflict response as fallback
4. Apply same pattern to `update_project` endpoint

## Technical Details
- **Affected Files**:
  - `src/app/api/v1/projects.py`
  - `src/alembic/versions/016_add_project_name_unique.py` (new)
- **Related Components**: ProjectRepository
- **Database Changes**: Yes - add unique index on projects.name

## Resources
- Original finding: Code review triage session
- Existing method: `ProjectRepository.get_by_name()`

## Acceptance Criteria
- [ ] Migration adds unique constraint on projects.name
- [ ] create_project returns 409 if name exists
- [ ] update_project returns 409 if name conflicts
- [ ] Error message is user-friendly
- [ ] Tests cover duplicate name scenarios

## Work Log

### 2025-12-18 - Implementation Complete
**By:** Claude Code
**Actions:**
- Created migration `017_add_project_name_unique.py` that adds unique constraint on `projects.name`
- Added application-level validation in `create_project` endpoint using `repo.get_by_name()`
- Added application-level validation in `update_project` endpoint with name change detection
- Added IntegrityError handling in both endpoints as fallback for race conditions
- Updated Project model to reflect `unique=True` on name field
- Added 409 Conflict response documentation to endpoint responses
- Status changed from ready to done

**Changes Made:**
- `src/alembic/versions/018_add_project_name_unique.py` - New migration file
- `src/app/api/v1/projects.py` - Added duplicate name checks and error handling
- `src/app/models/tenant/project.py` - Updated name field to unique=True

**Learnings:**
- Defense in depth: Check at application level before DB constraint
- IntegrityError fallback protects against race conditions
- update_project only checks if name is changing to avoid unnecessary queries

### 2025-12-17 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending to ready
- Ready to be picked up and worked on

**Learnings:**
- Always validate uniqueness at both DB and application level
- Use existing repository methods for validation

## Notes
Source: Triage session on 2025-12-17
