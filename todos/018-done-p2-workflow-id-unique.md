---
id: "018"
title: "workflow_id Unique Constraint"
status: pending
priority: p2
source: "REVIEW.md - MEDIUM #9"
category: data-integrity
---

# workflow_id Unique Constraint

## Problem

`workflow_executions.workflow_id` has an index but no unique constraint. Code assumes one row per workflow_id but the database doesn't enforce this.

## Risk

- **Duplicate records**: Multiple rows for same workflow_id possible
- **Query ambiguity**: `get_one_or_none` may raise on duplicates
- **Data corruption**: Updates may affect wrong record

## Verified Findings

| Location | Line | Issue |
|----------|------|-------|
| `src/app/models/public/workflow.py` | 18 | `index=True` but NOT `unique=True` |
| `src/alembic/versions/004_...` | 43-49 | Creates non-unique index only |

### Current Model

```python
class WorkflowExecution(Base):
    workflow_id: Mapped[str] = mapped_column(
        String(255),
        index=True,  # Has index
        # Missing: unique=True
    )
```

## Fix

1. Add `unique=True` to model
2. Create migration to add unique constraint

### Code Changes

**src/app/models/public/workflow.py:**
```python
workflow_id: Mapped[str] = mapped_column(
    String(255),
    unique=True,  # Add unique constraint
    index=True,
)
```

**New Migration:**
```python
# src/alembic/versions/014_add_workflow_id_unique.py
def upgrade() -> None:
    # Drop existing non-unique index
    op.drop_index("ix_workflow_executions_workflow_id", "workflow_executions")
    # Create unique constraint (implicitly creates unique index)
    op.create_unique_constraint(
        "uq_workflow_executions_workflow_id",
        "workflow_executions",
        ["workflow_id"]
    )

def downgrade() -> None:
    op.drop_constraint("uq_workflow_executions_workflow_id", "workflow_executions")
    op.create_index("ix_workflow_executions_workflow_id", "workflow_executions", ["workflow_id"])
```

## Files to Modify

- `src/app/models/public/workflow.py`
- New: `src/alembic/versions/014_add_workflow_id_unique.py`

## Acceptance Criteria

- [ ] Model has `unique=True` on workflow_id
- [ ] Migration adds unique constraint
- [ ] Migration handles existing index gracefully
- [ ] Verify no duplicate workflow_ids exist before migration
