---
status: ready
priority: p2
issue_id: "008"
tags: [architecture, temporal, state-management, reliability]
dependencies: []
---

# Temporal Workflow State Not Tracked in Database

## Problem Statement
When workflows are started, there's no record in the database linking the workflow_id to the tenant/user. If workflow fails to start or Temporal is unavailable, there's no way to query pending provisioning, resume failed workflows, or detect orphaned data.

## Findings
- No database record linking workflow_id to entities
- Location: `src/app/services/registration_service.py:60-71`
- Location: `src/app/services/tenant_service.py:47`
- User/tenant can be created but workflow start may fail
- No visibility into "stuck" provisioning states
- No mechanism to retry failed workflow starts

## Proposed Solutions

### Option 1: Add workflow tracking table (RECOMMENDED)
- **Pros**: Full visibility, enables retry logic, audit trail
- **Cons**: Additional table, migration required
- **Effort**: Large (6-8 hours)
- **Risk**: Low

Implementation:
```python
# New model
class WorkflowExecution(SQLModel, table=True):
    __tablename__ = "workflow_executions"
    __table_args__ = {"schema": "public"}

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    workflow_id: str = Field(max_length=255, unique=True, index=True)
    workflow_type: str = Field(max_length=100)  # "tenant_provisioning", etc.
    entity_type: str  # "tenant", "user"
    entity_id: UUID = Field(index=True)
    status: str = Field(default="pending")  # pending, running, completed, failed
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

# Usage in service
workflow_exec = WorkflowExecution(
    workflow_id=workflow_id,
    workflow_type="tenant_provisioning",
    entity_type="tenant",
    entity_id=tenant.id,
    status="pending"
)
session.add(workflow_exec)
await session.commit()

# Then start workflow and update status to "running"
```

### Option 2: Store workflow_id directly on entity
- **Pros**: Simpler, no new table
- **Cons**: Less flexible, no history
- **Effort**: Medium (3-4 hours)
- **Risk**: Low

## Recommended Action
Implement Option 1 - dedicated workflow tracking table for full visibility

## Technical Details
- **Affected Files**:
  - New model: `src/app/models/public.py`
  - New migration file
  - `src/app/services/registration_service.py`
  - `src/app/services/tenant_service.py`
  - `src/app/temporal/activities.py` (update workflow status on completion)
- **Related Components**: All Temporal workflows, admin dashboard
- **Database Changes**: Yes - new `workflow_executions` table

## Resources
- Original finding: Code review triage session
- Temporal visibility: https://docs.temporal.io/visibility

## Acceptance Criteria
- [ ] WorkflowExecution model created
- [ ] Migration adds workflow_executions table
- [ ] Workflow record created before workflow start
- [ ] Status updated to "running" after successful start
- [ ] Status updated to "completed" or "failed" by activities
- [ ] Error message captured on failure
- [ ] API endpoint to list workflow executions (admin)
- [ ] Background job to detect stuck workflows (optional)
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 IMPORTANT
- Estimated effort: Large (6-8 hours)

**Learnings:**
- Database should be source of truth for workflow state
- Temporal visibility is useful but database enables custom queries
- Two-phase commit: record intent first, then execute

## Notes
Source: Triage session on 2025-12-04
