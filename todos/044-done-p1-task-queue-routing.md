---
status: pending
priority: p1
issue_id: "044"
tags: [temporal, routing, scaling, multi-tenant]
dependencies: []
---

# Add Task Queue Routing Module

## Problem Statement

All 4 workflows share a single `main-queue`, causing:
- **Noisy neighbor problems**: Heavy tenant provisioning starves token cleanup
- **No tenant isolation**: One tenant's surge affects all others
- **Coarse autoscaling**: Can't scale provisioning workers separately from cleanup
- **No workload-specific tuning**: Can't tune concurrency per workload type

## Findings

- **Current config**: `src/app/core/config.py:99`
  ```python
  temporal_task_queue: str = "main-queue"  # Single shared queue
  ```
- **All workflows use same queue**: `src/app/temporal/worker.py:77`
  ```python
  task_queue=settings.temporal_task_queue
  ```
- **4 workflow types compete**: UserOnboarding, TenantProvisioning, TenantDeletion, TokenCleanup

## Proposed Solutions

### Option 1: Create routing.py module with tenant-based sharding (Primary solution)
- **Pros**: Enables workload isolation; tenant fairness; future scaling flexibility
- **Cons**: Requires worker deployment changes (later todo)
- **Effort**: Medium (1-2 hours)
- **Risk**: Low (backward compatible with shards=1)

**1. Add config settings:**
```python
# src/app/core/config.py - add after temporal_task_queue
temporal_queue_prefix: str = "saas"
temporal_queue_shards: int = 1  # Start with 1 for backward compatibility, scale to 32/64
```

**2. Create routing module:**
```python
# src/app/temporal/routing.py
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

from temporalio.common import Priority


class QueueKind(StrEnum):
    """Workflow workload types for queue routing.

    Simple and extensible - start with 2 kinds, add more as needed.
    """
    TENANT = "tenant"  # All tenant-scoped workflows (provisioning, deletion, onboarding)
    JOBS = "jobs"      # System-wide background jobs (cleanup, scheduled tasks)
    # Future: ENTITY = "entity", NOTIFICATIONS = "notifications", BILLING = "billing"


@dataclass(frozen=True)
class TemporalRoute:
    """Routing result for workflow execution."""
    namespace: str
    task_queue: str
    priority: Priority | None = None


def _stable_shard(key: str, shards: int) -> int:
    """Compute stable shard from key using SHA256 (not Python hash())."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % max(1, shards)


def task_queue_name(prefix: str, kind: QueueKind, shard: int) -> str:
    """Generate task queue name: {prefix}.{kind}.{shard:02d}"""
    return f"{prefix}.{kind}.{shard:02d}"


def route_for_tenant(
    *,
    tenant_id: str,
    namespace: str,
    prefix: str,
    shards: int,
    kind: QueueKind,
    fairness_weight: int = 1,
) -> TemporalRoute:
    """
    Get routing info for a tenant-scoped workflow.

    Args:
        tenant_id: UUID string for tenant
        namespace: Temporal namespace
        prefix: Queue name prefix (e.g., "saas")
        shards: Number of queue shards (1, 32, 64)
        kind: Workload type for queue selection
        fairness_weight: Priority weight (higher = more capacity)

    Returns:
        TemporalRoute with task_queue and optional fairness priority
    """
    shard = _stable_shard(tenant_id, shards)
    tq = task_queue_name(prefix, kind, shard)

    # Task Queue Fairness uses Priority.fairness_key / fairness_weight
    priority = Priority(fairness_key=tenant_id, fairness_weight=fairness_weight)

    return TemporalRoute(namespace=namespace, task_queue=tq, priority=priority)


def route_for_system_job(
    *,
    namespace: str,
    prefix: str,
    kind: QueueKind = QueueKind.JOBS,
) -> TemporalRoute:
    """
    Get routing info for system-level jobs (not tenant-scoped).

    Uses shard 00 for predictable routing.
    """
    tq = task_queue_name(prefix, kind, shard=0)
    return TemporalRoute(namespace=namespace, task_queue=tq)
```

## Recommended Action

Implement Option 1 with `shards=1` initially (backward compatible), then increment to 32/64 after worker scaling (todo 049).

## Technical Details

- **Files to create**:
  - `src/app/temporal/routing.py`
- **Files to modify**:
  - `src/app/core/config.py`
- **Related Components**: All workflow start sites, worker deployment
- **Database Changes**: No

## Resources

- Original finding: REVIEW.md - Critical #1
- Temporal docs: Task Queue Fairness, Priority class

## Acceptance Criteria

- [ ] `routing.py` module created with QueueKind enum and routing functions
- [ ] Config settings added: `temporal_queue_prefix`, `temporal_queue_shards`
- [ ] `_stable_shard()` uses SHA256 for cross-process consistency
- [ ] `route_for_tenant()` returns correct queue names and fairness priority
- [ ] `route_for_system_job()` for non-tenant workflows
- [ ] Unit tests for routing logic (see todo 051)

## Work Log

### 2025-12-17 - Initial Discovery
**By:** Claude Code Review
**Actions:**
- Issue discovered during REVIEW.md Temporal review
- Categorized as CRITICAL (scaling foundation)
- Estimated effort: Medium

**Learnings:**
- Temporal scheduling is per task queue
- SHA256 hashing ensures stable tenant→shard mapping across processes
- Start with shards=1 for safe rollout

## Notes

Source: REVIEW.md Temporal implementation review

Migration note: With shards=1, all tenants route to `{prefix}.{kind}.00`, preserving current behavior. Existing `main-queue` workers continue working until deprecated.

**Workflow → QueueKind Mapping:**
| Workflow | QueueKind | Why |
|----------|-----------|-----|
| TenantProvisioningWorkflow | `TENANT` | Tenant-scoped, needs isolation |
| TenantDeletionWorkflow | `TENANT` | Tenant-scoped, needs isolation |
| UserOnboardingWorkflow | `TENANT` | User belongs to tenant |
| TokenCleanupWorkflow | `JOBS` | System-wide scheduled job |
