from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

try:
    from temporalio.common import Priority
except ImportError:
    # Priority was added in temporalio 1.16.0 (Aug 2025)
    # For older versions, provide a placeholder dataclass
    @dataclass(frozen=True)
    class Priority:  # type: ignore[no-redef]
        """Placeholder Priority class for temporalio < 1.16.0."""

        fairness_key: str = ""
        fairness_weight: int = 1


class QueueKind(StrEnum):
    """Workflow workload types for queue routing.

    Simple and extensible - start with 2 kinds, add more as needed.
    """

    TENANT = "tenant"  # All tenant-scoped workflows (provisioning, deletion, onboarding)
    JOBS = "jobs"  # System-wide background jobs (cleanup, scheduled tasks)
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
