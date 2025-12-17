---
status: pending
priority: p2
issue_id: "050"
tags: [temporal, multi-tenant, safety, contract]
dependencies: ["044"]
---

# Tenant Context Contract

## Problem Statement

As workflows grow, "forgot to pass tenant_id" becomes a common bug. Current activity inputs are inconsistent - some have `tenant_id`, some have `schema_name`, some have both. This leads to:
- Cross-tenant data access bugs
- Missing tenant context in logs
- Inconsistent fairness weighting
- Hard-to-debug multi-tenant issues

## Findings

Current activity inputs (inconsistent patterns):
- `GetTenantInput(tenant_id)` - has tenant_id
- `RunMigrationsInput(schema_name)` - has schema_name only
- `CreateMembershipInput(user_id, tenant_id)` - has tenant_id
- `DropSchemaInput(schema_name)` - has schema_name only
- `UpdateTenantStatusInput(tenant_id, status)` - has tenant_id
- `SoftDeleteTenantInput(tenant_id)` - has tenant_id
- Cleanup activities - no tenant context (system-wide)

## Proposed Solutions

### Option 1: Create standardized TenantCtx dataclass (Primary solution)
- **Pros**: Consistent contract; enables fairness weighting; prevents forgotten context
- **Cons**: Requires updating existing activity inputs
- **Effort**: Medium (2-3 hours)
- **Risk**: Low (additive change, backward compatible)

**1. Create shared context contract:**
```python
# src/app/temporal/context.py
from dataclasses import dataclass
from typing import Final

# Plan-based fairness weights
PLAN_WEIGHTS: Final[dict[str, int]] = {
    "free": 1,
    "pro": 3,
    "enterprise": 10,
}


@dataclass(frozen=True)
class TenantCtx:
    """
    Standardized tenant context for all tenant-scoped activities.

    All tenant-scoped activity inputs should include this context
    to ensure consistent tenant isolation and fairness weighting.
    """
    tenant_id: str
    schema_name: str
    plan: str | None = None  # For fairness weighting

    @property
    def fairness_weight(self) -> int:
        """Get fairness weight based on plan tier."""
        return PLAN_WEIGHTS.get(self.plan or "free", 1)


def get_fairness_weight(plan: str | None) -> int:
    """Get fairness weight for a plan tier."""
    return PLAN_WEIGHTS.get(plan or "free", 1)
```

**2. Update activity inputs to include TenantCtx:**
```python
# Before (inconsistent):
@dataclass
class RunMigrationsInput:
    schema_name: str

# After (consistent):
@dataclass
class RunMigrationsInput:
    ctx: TenantCtx

    # For backward compatibility during migration:
    @classmethod
    def from_schema(cls, schema_name: str, tenant_id: str) -> "RunMigrationsInput":
        return cls(ctx=TenantCtx(tenant_id=tenant_id, schema_name=schema_name))
```

**3. Update routing to use plan-based fairness:**
```python
# src/app/temporal/routing.py
from src.app.temporal.context import TenantCtx

def route_for_tenant(
    *,
    ctx: TenantCtx,  # Use context instead of individual fields
    namespace: str,
    prefix: str,
    shards: int,
    kind: QueueKind,
) -> TemporalRoute:
    shard = _stable_shard(ctx.tenant_id, shards)
    tq = task_queue_name(prefix, kind, shard)
    priority = Priority(
        fairness_key=ctx.tenant_id,
        fairness_weight=ctx.fairness_weight,
    )
    return TemporalRoute(namespace=namespace, task_queue=tq, priority=priority)
```

**4. Workflow usage pattern:**
```python
@workflow.defn
class TenantProvisioningWorkflow:
    @workflow.run
    async def run(self, tenant_id: str, user_id: str | None = None) -> str:
        # Get tenant info to build context
        tenant_info = await workflow.execute_activity(
            get_tenant_info,
            GetTenantInput(tenant_id=tenant_id),
            ...
        )

        # Build context for all subsequent activities
        ctx = TenantCtx(
            tenant_id=tenant_id,
            schema_name=tenant_info.schema_name,
            plan=tenant_info.plan,  # If available
        )

        # Use context for all tenant-scoped activities
        await workflow.execute_activity(
            run_tenant_migrations,
            RunMigrationsInput(ctx=ctx),
            ...
        )
```

## Recommended Action

Implement Option 1 incrementally:
1. Create `context.py` with TenantCtx
2. Add TenantCtx to new activities
3. Gradually migrate existing activities

## Technical Details

- **Files to create**:
  - `src/app/temporal/context.py`
- **Files to modify**:
  - Activity input dataclasses (gradually)
  - `src/app/temporal/routing.py` (use ctx.fairness_weight)
- **Related Components**: All tenant-scoped workflows and activities
- **Database Changes**: No

## Resources

- Original finding: REVIEW.md - Medium #7
- Temporal docs: Task Queue Fairness, Priority

## Acceptance Criteria

- [ ] `TenantCtx` dataclass created with tenant_id, schema_name, plan
- [ ] `fairness_weight` property computes from plan tier
- [ ] `PLAN_WEIGHTS` constant defines tier weights
- [ ] New activities use TenantCtx in inputs
- [ ] Documentation explains context contract
- [ ] Routing uses ctx.fairness_weight when available

## Work Log

### 2025-12-17 - Initial Discovery
**By:** Claude Code Review
**Actions:**
- Issue discovered during REVIEW.md Temporal review
- Categorized as MEDIUM (safety)
- Estimated effort: Medium

**Learnings:**
- Consistent context prevents "forgot tenant_id" bugs
- Plan-based fairness enables soft isolation
- Context object is easier to extend than individual fields

## Notes

Source: REVIEW.md Temporal implementation review

Migration note: Can be done incrementally. New activities use TenantCtx immediately. Existing activities migrate during their next modification.
