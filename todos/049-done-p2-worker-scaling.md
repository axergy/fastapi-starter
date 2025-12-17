---
status: done
priority: p2
issue_id: "049"
tags: [temporal, operations, kubernetes, scaling]
dependencies: ["044"]
---

# Worker Scaling Architecture

## Problem Statement

Single worker process on single queue doesn't scale:
- Can't tune concurrency per workload type
- Provisioning and cleanup compete for same resources
- No horizontal scaling strategy
- Worker settings are one-size-fits-all

## Findings

- **Current worker**: `src/app/temporal/worker.py:75-97`
  - Single Worker instance
  - Polls one queue (`settings.temporal_task_queue`)
  - All workflows and activities registered together
- **No scaling separation**: Provisioning (heavy) and cleanup (light) share resources
- **No deployment templates**: Kubernetes manifests not present

## Proposed Solutions

### Option 1: Multi-worker architecture with K8s deployments (Primary solution)
- **Pros**: Workload isolation; independent scaling; tuned concurrency
- **Cons**: More complex deployment; multiple processes
- **Effort**: Large (4-6 hours)
- **Risk**: Medium (deployment changes)

**A. Update worker.py for multi-queue support:**
```python
# src/app/temporal/worker.py
import asyncio
from typing import Sequence

from temporalio.client import Client
from temporalio.worker import Worker

from src.app.core.config import get_settings
from src.app.temporal.routing import QueueKind, task_queue_name


async def create_worker(
    client: Client,
    task_queue: str,
    workflows: Sequence[type],
    activities: Sequence,
    *,
    max_concurrent_activities: int = 100,
    max_concurrent_workflow_tasks: int = 100,
) -> Worker:
    """Create a worker with tuned settings."""
    return Worker(
        client,
        task_queue=task_queue,
        workflows=list(workflows),
        activities=list(activities),
        max_concurrent_activities=max_concurrent_activities,
        max_concurrent_workflow_tasks=max_concurrent_workflow_tasks,
    )


async def run_tenant_workers(client: Client) -> None:
    """Run workers for tenant queues (all tenant-scoped workflows)."""
    settings = get_settings()
    workers = []

    for shard in range(settings.temporal_queue_shards):
        tq = task_queue_name(settings.temporal_queue_prefix, QueueKind.TENANT, shard)
        worker = await create_worker(
            client,
            tq,
            workflows=[
                TenantProvisioningWorkflow,
                TenantDeletionWorkflow,
                UserOnboardingWorkflow,
            ],
            activities=[...],  # tenant activities
            max_concurrent_activities=20,
            max_concurrent_workflow_tasks=20,
        )
        workers.append(worker)

    await asyncio.gather(*(w.run() for w in workers))


async def run_jobs_workers(client: Client) -> None:
    """Run workers for job queues (system-wide background tasks)."""
    settings = get_settings()
    tq = task_queue_name(settings.temporal_queue_prefix, QueueKind.JOBS, 0)
    worker = await create_worker(
        client,
        tq,
        workflows=[TokenCleanupWorkflow],
        activities=[...],  # cleanup activities
        max_concurrent_activities=50,
        max_concurrent_workflow_tasks=50,
    )
    await worker.run()
```

**B. Kubernetes deployment templates:**

```yaml
# deploy/k8s/worker-tenant.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: temporal-worker-tenant
spec:
  replicas: 2  # Scale based on tenant operations load
  selector:
    matchLabels:
      app: temporal-worker
      workload: tenant
  template:
    metadata:
      labels:
        app: temporal-worker
        workload: tenant
    spec:
      containers:
        - name: worker
          image: app:latest
          command: ["python", "-m", "src.app.temporal.worker", "--workload", "tenant"]
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
          env:
            - name: TEMPORAL_QUEUE_SHARDS
              value: "1"  # Start with 1, scale to 32/64
```

```yaml
# deploy/k8s/worker-jobs.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: temporal-worker-jobs
spec:
  replicas: 1  # Jobs are less frequent (cleanup, cron)
  selector:
    matchLabels:
      app: temporal-worker
      workload: jobs
  template:
    # ... similar structure
```

**C. CLI argument parsing in worker:**
```python
# src/app/temporal/worker.py
import argparse

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workload",
        choices=["tenant", "jobs", "all"],
        default="all",
        help="Worker workload type",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    settings = get_settings()
    client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)

    if args.workload == "tenant":
        await run_tenant_workers(client)
    elif args.workload == "jobs":
        await run_jobs_workers(client)
    elif args.workload == "all":
        # Development mode: run all in one process
        await asyncio.gather(
            run_tenant_workers(client),
            run_jobs_workers(client),
        )
```

## Recommended Action

Implement Option 1 in phases:
1. First: Add multi-queue support to worker.py
2. Then: Create K8s templates
3. Finally: Deploy separate worker pools

## Technical Details

- **Files to modify**:
  - `src/app/temporal/worker.py` (add multi-queue support, CLI args)
- **Files to create**:
  - `deploy/k8s/worker-tenant.yaml`
  - `deploy/k8s/worker-jobs.yaml`
- **Related Components**: routing.py, Kubernetes deployment
- **Database Changes**: No

## Resources

- Original finding: REVIEW.md - High #6
- Temporal docs: Worker tuning (max_concurrent_*, max_cached_workflows)
- Kubernetes: Deployment autoscaling

## Acceptance Criteria

- [x] worker.py supports `--workload` CLI argument
- [x] `create_worker()` helper with tunable concurrency
- [x] Separate functions for provisioning vs jobs workers
- [x] K8s deployment templates for each worker type
- [x] Development mode (`--workload all`) runs everything
- [x] Health server includes workload type in response

## Work Log

### 2025-12-17 - Initial Discovery
**By:** Claude Code Review
**Actions:**
- Issue discovered during REVIEW.md Temporal review
- Categorized as HIGH (operations)
- Estimated effort: Large

**Learnings:**
- Workers are per task queue - scale by adding replicas
- Provisioning: low concurrency, long timeouts
- Jobs: higher concurrency, quick tasks
- Entity: tuned caching for replay performance

### 2025-12-17 - Implementation Complete
**By:** Claude Code
**Actions:**
- Updated `src/app/temporal/worker.py` with multi-queue support:
  - Added `parse_args()` function with `--workload` CLI argument
  - Created `create_worker()` helper with tunable concurrency settings
  - Implemented `run_tenant_workers()` for tenant-scoped workflows (20 max concurrent)
  - Implemented `run_jobs_workers()` for system-level jobs (50 max concurrent)
  - Updated `run_health_server()` to include workload type in response
  - Modified `main()` to support three modes: tenant, jobs, all (dev mode)
- Created K8s deployment templates:
  - `deploy/k8s/worker-tenant.yaml`: 2 replicas, 512Mi-1Gi memory, HPA enabled
  - `deploy/k8s/worker-jobs.yaml`: 1 replica, 256Mi-512Mi memory, HPA enabled
- Verified implementation:
  - Python syntax check passed
  - CLI help shows workload argument correctly
  - Backward compatible: existing `main()` still works with default `--workload all`

**Implementation Details:**
- Tenant workers: Lower concurrency (20) for heavy DB operations (provisioning, deletion)
- Jobs workers: Higher concurrency (50) for lightweight cleanup tasks
- Automatic shard-aware worker creation based on `TEMPORAL_QUEUE_SHARDS` setting
- Health endpoints include workload type and all task queues being polled
- K8s manifests include complete environment configuration, health checks, HPA, and pod anti-affinity

**Learnings:**
- Multi-queue architecture enables independent scaling per workload type
- Development mode (`--workload all`) maintains backward compatibility
- Health server now provides better observability with workload metadata

## Notes

Source: REVIEW.md Temporal implementation review

Monitoring note: Track schedule-to-start latency per queue to identify scaling needs. Temporal metrics: `temporal_schedule_to_start_latency`.
