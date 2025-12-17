"""
Tenant context contract for Temporal workflows and activities.

Provides standardized tenant context to prevent cross-tenant data access bugs,
ensure consistent fairness weighting, and improve observability.

Usage Example:
    ```python
    from app.temporal.context import TenantCtx

    # In workflow: build context once, use everywhere
    ctx = TenantCtx(
        tenant_id="tenant_123",
        schema_name="tenant_123_schema",
        plan="pro"  # Optional, enables fairness weighting
    )

    # Pass to all tenant-scoped activities
    @dataclass
    class RunMigrationsInput:
        ctx: TenantCtx

    await workflow.execute_activity(
        run_tenant_migrations,
        RunMigrationsInput(ctx=ctx),
        ...
    )

    # Use fairness weight for task routing
    priority = Priority(
        fairness_key=ctx.tenant_id,
        fairness_weight=ctx.fairness_weight,
    )
    ```

Migration Note:
    This is an incremental migration. New activities should use TenantCtx
    immediately. Existing activities will be migrated during their next
    modification to avoid breaking changes.
"""

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

    Attributes:
        tenant_id: Unique tenant identifier for isolation and fairness key
        schema_name: Database schema name for query routing (optional for some activities)
        plan: Optional plan tier (free/pro/enterprise) for fairness weighting

    Properties:
        fairness_weight: Plan-based priority weight for task queue fairness

    Design Notes:
        - Frozen dataclass ensures immutability (prevents accidental modification)
        - tenant_id is always required
        - schema_name is optional (some activities like update_tenant_status don't need it)
        - Context is built once in workflow, passed to all activities
        - Prevents "forgot tenant_id" bugs through consistent contract
    """

    tenant_id: str
    schema_name: str | None = None  # Optional - not all activities need schema
    plan: str | None = None  # For fairness weighting

    @property
    def fairness_weight(self) -> int:
        """
        Get fairness weight based on plan tier.

        Returns plan-specific weight for Temporal task queue priority:
        - free: 1 (baseline)
        - pro: 3 (3x more weight than free)
        - enterprise: 10 (10x more weight than free)

        Used in Priority(fairness_key=tenant_id, fairness_weight=weight)
        to implement soft isolation through weighted fair queuing.

        Returns:
            int: Fairness weight for this tenant's plan tier
        """
        return PLAN_WEIGHTS.get(self.plan or "free", 1)


def get_fairness_weight(plan: str | None) -> int:
    """
    Get fairness weight for a plan tier.

    Helper function for computing fairness weight without TenantCtx instance.
    Useful during workflow initialization or routing decisions.

    Args:
        plan: Plan tier (free/pro/enterprise) or None

    Returns:
        int: Fairness weight (1 for free/None, 3 for pro, 10 for enterprise)

    Example:
        ```python
        weight = get_fairness_weight("pro")  # Returns 3
        priority = Priority(fairness_key=tenant_id, fairness_weight=weight)
        ```
    """
    return PLAN_WEIGHTS.get(plan or "free", 1)
