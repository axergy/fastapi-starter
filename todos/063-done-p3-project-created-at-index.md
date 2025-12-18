---
status: done
priority: p3
issue_id: "063"
tags: [performance, database, index]
dependencies: []
---

# Missing Index on Project created_at for Pagination

## Problem Statement
The `ProjectRepository.list_all()` method orders by `created_at DESC` but there's no index on this column. For tenants with many projects, this could cause slow queries as PostgreSQL must sort all rows.

## Findings
- `list_all()` orders by `created_at DESC`
- Only index is on `name` column
- Location: `src/alembic/versions/015_add_tenant_projects.py:37`
- Large datasets will require full table scan for sorting

## Proposed Solutions

### Option 1: Add index on created_at
- **Pros**: Faster pagination queries, better scalability
- **Cons**: Slight write overhead, additional storage
- **Effort**: Small (10 minutes)
- **Risk**: Low

## Recommended Action
Create migration to add index:

```python
# 016_add_project_created_at_index.py (or combine with other project fixes)

def upgrade() -> None:
    if not is_tenant_migration():
        return
    op.create_index(
        "ix_projects_created_at",
        "projects",
        ["created_at"],
        unique=False
    )

def downgrade() -> None:
    if not is_tenant_migration():
        return
    op.drop_index("ix_projects_created_at", table_name="projects")
```

Alternatively, add `index=True` to model field:

```python
created_at: datetime = Field(default_factory=utc_now, index=True)
```

## Technical Details
- **Affected Files**:
  - New migration file OR update existing 015 migration
  - Optionally: `src/app/models/tenant/project.py`
- **Related Components**: ProjectRepository.list_all()
- **Database Changes**: Yes - add index

## Resources
- Original finding: Code review triage session
- PostgreSQL index documentation

## Acceptance Criteria
- [ ] Index exists on projects.created_at
- [ ] Pagination queries use index (verify with EXPLAIN)
- [ ] Migration runs on all tenant schemas
- [ ] No performance regression on writes

## Work Log

### 2025-12-17 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending to ready
- Ready to be picked up and worked on

**Learnings:**
- ORDER BY columns should be indexed for pagination
- Consider query patterns when designing indexes
- Index overhead is usually worth it for read-heavy tables

### 2025-12-18 - Implementation Complete
**By:** Claude Code
**Actions:**
- Created migration `src/alembic/versions/017_add_project_created_at_index.py`
- Added index on `projects.created_at` column
- Configured as tenant migration using `is_tenant_migration()` check
- Migration includes both upgrade and downgrade functions
- Status changed from ready to done

**Implementation:**
- Migration revision: 017
- Revises: 016
- Index name: `ix_projects_created_at`
- Table: `projects`
- Column: `created_at`
- Non-unique index for improved pagination performance

## Notes
Source: Triage session on 2025-12-17
Implementation: Created new migration file 017 (migration 016 already existed for tenant slug normalization)
