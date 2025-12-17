High-level summary

Right now your Temporal integration works, but it’s sitting on a couple scaling/isolation “fault lines” that will bite you hard at thousands → millions of workflows:

Everything shares one task queue (settings.temporal_task_queue), so provisioning, deletions, cleanup, and future entity workflows all compete for the same worker capacity and scheduling fairness. That’s a classic “noisy neighbor” setup.

code



code

Namespace is defined in settings, but not actually used in Client.connect in API/worker code, which makes multi-environment and future sharded-namespace routing harder than it needs to be.

code



code



code

Workflow/activities are already trending toward “god files” (workflows.py, activities.py). You’re doing the right things (deterministic orchestration, activities for side effects), but you need module boundaries now before you add 10+ more workflows/updates/signals.

code

For true “millions of workflows” scale, you need to engineer around history/event limits and APS. Temporal will warn and eventually fail executions that grow too large (default limits), so long-running entity workflows must be built with Continue-As-New and low-history patterns.

Strong multi-tenancy in Temporal comes from Namespaces as isolation units, plus queue/routing/fairness controls; without those, you get cross-tenant resource contention even if your DB isolation is perfect.

Top recommended changes (pragmatic, high ROI):

Split task queues by workload + shard by tenant (hash-based), and (optionally) enable Task Queue Fairness using Priority(fairness_key=tenant_id) + server-side queue config limits.

Make namespace routing real: connect using settings.temporal_namespace everywhere, and introduce a tiny “routing layer” so you can later add namespace sharding (or per-enterprise namespace) without touching business code.

code

Modularize workflows now: “orchestrators” stay small, reusable steps live in workflow-step modules, and complex flows become child workflows. (You’ll avoid monolith workflow files.)

Adopt the long-running entity workflow template: Updates/Queries, Continue-As-New thresholds, and minimal event-history bloat using workflow.info().get_current_history_length() / is_continue_as_new_suggested().

Separate worker pools (deployment level): provisioning workers vs high-throughput entity/job workers, with tuned concurrency/caching. Workers are per task queue, so you scale by adding worker replicas per queue shard.

Prioritized refactor plan
CRITICAL
1) Stop using a single shared task queue (add workload queues + tenant sharding)

Issue / risk
Your worker runs everything on settings.temporal_task_queue.

code


That guarantees contention and makes it impossible to isolate provisioning (heavy, spiky) from high-volume entity workflows (constant, latency sensitive). It also makes autoscaling coarse and “noisy neighbor” behavior inevitable.

Why it matters for scale/isolation
Temporal scheduling is per task queue. If all tenants and workflow types share one queue, one tenant’s surge or one heavy workflow type can starve others. Even in a shared namespace, your best lever is routing to queues + worker pools.

Concrete implementation (minimal changes, big impact)

Add settings (keep backward compatibility with temporal_task_queue):

--- a/src/app/core/config.py
+++ b/src/app/core/config.py
@@
     # Temporal
     temporal_host: str = "localhost:7233"
     temporal_namespace: str = "default"
     temporal_task_queue: str = "main-queue"
+
+    # Temporal routing (scaling)
+    temporal_queue_prefix: str = "saas"
+    temporal_queue_shards: int = 64  # 16/32/64 are typical; start at 32 or 64


Create a routing module:

+++ b/src/app/temporal/routing.py
@@
+from __future__ import annotations
+
+import hashlib
+from dataclasses import dataclass
+from enum import StrEnum
+
+from temporalio.common import Priority
+
+
+class QueueKind(StrEnum):
+    PROVISIONING = "provisioning"
+    TENANT_OPS = "tenant_ops"
+    JOBS = "jobs"
+    ENTITY = "entity"
+
+
+@dataclass(frozen=True)
+class TemporalRoute:
+    namespace: str
+    task_queue: str
+    # Optional: used when Task Queue Fairness is enabled
+    priority: Priority | None = None
+
+
+def _stable_shard(key: str, shards: int) -> int:
+    # Stable across processes/releases (unlike Python hash()).
+    digest = hashlib.sha256(key.encode("utf-8")).digest()
+    return int.from_bytes(digest[:4], "big") % max(1, shards)
+
+
+def task_queue_name(prefix: str, kind: QueueKind, shard: int) -> str:
+    return f"{prefix}.{kind}.{shard:02d}"
+
+
+def route_for_tenant(
+    *,
+    tenant_id: str,
+    namespace: str,
+    prefix: str,
+    shards: int,
+    kind: QueueKind,
+    fairness_weight: int = 1,
+) -> TemporalRoute:
+    shard = _stable_shard(tenant_id, shards)
+    tq = task_queue_name(prefix, kind, shard)
+
+    # Task Queue Fairness uses Priority.fairness_key / fairness_weight
+    # (safe to pass even if you don't enable fairness yet; but you can keep it None)
+    prio = Priority(fairness_key=tenant_id, fairness_weight=fairness_weight)
+    return TemporalRoute(namespace=namespace, task_queue=tq, priority=prio)


Update workflow starts to use routing instead of one constant queue (example: tenant provisioning start):
Right now you hardcode task_queue=settings.temporal_task_queue.

code

--- a/src/app/tenants/service.py
+++ b/src/app/tenants/service.py
@@
 from src.app.temporal.client import get_temporal_client
+from src.app.temporal.routing import QueueKind, route_for_tenant
@@
             client = await get_temporal_client()
+            route = route_for_tenant(
+                tenant_id=str(tenant.id),
+                namespace=settings.temporal_namespace,
+                prefix=settings.temporal_queue_prefix,
+                shards=settings.temporal_queue_shards,
+                kind=QueueKind.PROVISIONING,
+                fairness_weight=1,  # later: map from plan
+            )
             await client.start_workflow(
                 "TenantProvisioningWorkflow.run",
                 args=[str(tenant.id), str(workflow_execution.id)],
                 id=workflow_id,
-                task_queue=settings.temporal_task_queue,
+                task_queue=route.task_queue,
+                # If you enable fairness: route.priority helps reduce noisy neighbor impact
+                priority=route.priority,
             )


Optional but recommended: enable Task Queue Fairness controls
Temporal supports fairness keys/weights via Priority(fairness_key=..., fairness_weight=...).
On the server, you can configure default per-fairness-key RPS limits on a task queue (task-queue config set --fairness-key-rps-limit-default ...).
This is the cleanest “noisy neighbor” control that doesn’t explode task queue count.

2) Make namespace usage explicit everywhere (and add routing hooks for future sharding)

Issue / risk
You define temporal_namespace in settings, but the worker and API connect without it (defaults to whatever the SDK uses).

code



code



code


That’s a footgun when you add “prod vs staging” namespaces or when you shard namespaces for scale.

Why it matters
Namespaces are Temporal’s primary isolation boundary.
Also, APS quotas are commonly set per namespace (Temporal Cloud), so namespace sharding is a real scaling tool.

Concrete changes

Update API client:

--- a/src/app/temporal/client.py
+++ b/src/app/temporal/client.py
@@
 async def get_temporal_client() -> Client:
@@
-        _client = await Client.connect(settings.temporal_host)
+        _client = await Client.connect(
+            settings.temporal_host,
+            namespace=settings.temporal_namespace,
+        )
         logger.info("Connected to Temporal")


Update worker connect:

--- a/src/app/temporal/worker.py
+++ b/src/app/temporal/worker.py
@@
-    client = await Client.connect(settings.temporal_host)
+    client = await Client.connect(
+        settings.temporal_host,
+        namespace=settings.temporal_namespace,
+    )


Next step (still simple): if you later do namespace sharding, convert get_temporal_client() into a tiny cached factory keyed by namespace (LRU dict + async lock). Your route_for_tenant() already returns namespace, so business code won’t change.

3) Fix worker registration drift (workflow execution tracking activity is imported but not registered)

Issue
workflows.py imports update_workflow_execution_status, but worker.py does not register it in the activities list.

code



code


The activity exists.

code

Why it matters
This becomes a production-only failure mode: workflow starts fine, then blows up when it tries to execute an activity the worker doesn’t serve.

Concrete fix

--- a/src/app/temporal/worker.py
+++ b/src/app/temporal/worker.py
@@
 from src.app.temporal.activities import (
@@
     update_tenant_status,
+    update_workflow_execution_status,
 )
@@
         activities=[
@@
             update_tenant_status,
+            update_workflow_execution_status,
         ],

HIGH
4) Modular workflow design: break “god workflow file” into orchestrators + reusable workflow-steps + child workflows

Issue / risk
You already have multiple workflows in a single workflows.py and multiple activities in one activities.py.

code


As you add signals/updates, this will become a “god module” with implicit coupling and accidental cross-tenant mistakes.

Why it matters

Maintainability: smaller modules, stable interfaces, easier versioning.

Replay safety: deterministic code is easiest to audit when workflows are small.

Reuse: consistent activity options, retry policies, and progress reporting.

Concrete refactor layout (Python SDK idiomatic)

src/app/temporal/
  activities/
    __init__.py
    tenant.py
    memberships.py
    workflow_executions.py
    cleanup.py
  workflows/
    __init__.py
    tenant_provisioning.py
    tenant_deletion.py
    cleanup.py
    _steps/
      tenant_steps.py
      common.py
  routing.py
  worker.py
  client.py


Example: move provisioning into a dedicated module + steps

src/app/temporal/workflows/_steps/common.py:

from __future__ import annotations
from datetime import timedelta
from temporalio.common import RetryPolicy

DEFAULT_RETRY = RetryPolicy(
    maximum_attempts=5,
    initial_interval=timedelta(seconds=1),
)

def short_activity_opts():
    return dict(
        start_to_close_timeout=timedelta(seconds=10),
        retry_policy=DEFAULT_RETRY,
    )

def medium_activity_opts():
    return dict(
        start_to_close_timeout=timedelta(seconds=60),
        retry_policy=DEFAULT_RETRY,
    )


src/app/temporal/workflows/_steps/tenant_steps.py:

from __future__ import annotations
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.app.models.public import TenantStatus
    from src.app.temporal.activities import (
        GetTenantInput,
        UpdateTenantStatusInput,
        RunMigrationsInput,
        CreateMembershipInput,
        get_tenant_info,
        update_tenant_status,
        run_tenant_migrations,
        create_admin_membership,
    )

async def ensure_schema_provisioned(*, tenant_id: str, workflow_execution_id: str) -> str:
    tenant = await workflow.execute_activity(
        get_tenant_info,
        GetTenantInput(tenant_id=tenant_id),
        start_to_close_timeout=timedelta(seconds=30),
        retry_policy=RetryPolicy(maximum_attempts=3),
    )

    await workflow.execute_activity(
        update_tenant_status,
        UpdateTenantStatusInput(tenant_id=tenant_id, status=TenantStatus.PROVISIONING),
        start_to_close_timeout=timedelta(seconds=10),
        retry_policy=RetryPolicy(maximum_attempts=3),
    )

    await workflow.execute_activity(
        run_tenant_migrations,
        RunMigrationsInput(tenant_id=tenant_id, schema_name=tenant.schema_name),
        start_to_close_timeout=timedelta(minutes=10),
        retry_policy=RetryPolicy(maximum_attempts=1),
    )

    return tenant.schema_name

async def ensure_admin_membership(*, tenant_id: str, user_id: str) -> None:
    await workflow.execute_activity(
        create_admin_membership,
        CreateMembershipInput(tenant_id=tenant_id, user_id=user_id),
        start_to_close_timeout=timedelta(seconds=30),
        retry_policy=RetryPolicy(maximum_attempts=3),
    )


Then src/app/temporal/workflows/tenant_provisioning.py stays tiny:

from temporalio import workflow

from src.app.temporal.workflows._steps.tenant_steps import (
    ensure_schema_provisioned,
    ensure_admin_membership,
)

@workflow.defn
class TenantProvisioningWorkflow:
    @workflow.run
    async def run(self, tenant_id: str, workflow_execution_id: str) -> None:
        schema = await ensure_schema_provisioned(
            tenant_id=tenant_id,
            workflow_execution_id=workflow_execution_id,
        )
        workflow.logger.info(f"Provisioned schema: {schema}")


Child workflows vs steps
Use child workflows when:

The phase is long-running or needs independent retries/visibility

You want per-phase history boundaries (parent history stays small)

You want modular deployment/versioning boundaries

Use steps (pure async functions) when:

It’s a short sequence and you mainly want code organization

5) Build the “millions of workflows” entity template (Updates/Queries + Continue-As-New + low-history)

Issue / risk
Long-running workflows (entity lifecycles) will eventually hit history limits if you rely on signals/events for every state change. Temporal has workflow execution limits and warns before failure (default warning at ~10k events).

Why it matters

History growth increases replay time, cache pressure, and worker CPU

Eventually the workflow fails when it exceeds limits

You also need to manage APS: lots of events/signals/starts drive APS load.

Concrete template

from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from temporalio import workflow

@dataclass(frozen=True)
class EntityCtx:
    tenant_id: str
    entity_id: str

@dataclass(frozen=True)
class Command:
    kind: str
    payload: dict

@workflow.defn
class EntityWorkflow:
    def __init__(self) -> None:
        self._pending: list[Command] = []
        self._done: bool = False

    @workflow.run
    async def run(self, ctx: EntityCtx) -> None:
        # Prefer queries for reads (no history events). Use updates/signals sparingly.
        while not self._done:
            await workflow.wait_condition(lambda: bool(self._pending) or self._done, timeout=timedelta(minutes=5))

            # process commands
            while self._pending:
                cmd = self._pending.pop(0)
                await self._apply(ctx, cmd)

            # Guardrails: history bloat prevention
            info = workflow.info()
            if info.is_continue_as_new_suggested() or info.get_current_history_length() > 8000:
                workflow.logger.info("Continuing as new to cap history")
                raise workflow.ContinueAsNewError(ctx)

    @workflow.update
    async def submit(self, cmd: Command) -> None:
        self._pending.append(cmd)

    @workflow.query
    def status(self) -> dict:
        return {"pending": len(self._pending), "done": self._done}

    async def _apply(self, ctx: EntityCtx, cmd: Command) -> None:
        # Do real side effects in activities. Keep workflow logic minimal/deterministic.
        workflow.logger.info(f"Apply {cmd.kind} for {ctx.tenant_id}/{ctx.entity_id}")


This uses workflow.info().get_current_history_length() and is_continue_as_new_suggested() for safe Continue-As-New decisions.
And it aligns with Temporal execution limit realities.

6) Worker scaling: run worker pools per queue shard (and tune caching/concurrency)

Issue / risk
One worker process on one queue won’t scale linearly. Also, provisioning workloads should not share worker settings with entity workloads.

Why it matters
Temporal workers are tied to a task queue: “A Worker Entity is connected to one Task Queue.”
So you scale by:

more worker replicas per queue shard, and/or

more queue shards
And you isolate by having different worker deployments per workload type.

Concrete approach

Option A (simple, Kubernetes-friendly): separate deployments

worker-provisioning: polls saas.provisioning.* shards, low concurrency, large activity timeouts

worker-entity: polls saas.entity.* shards, higher concurrency, tuned caching

worker-jobs: polls saas.jobs.* shards

Option B (single process, multiple Worker instances)
Temporal allows multiple worker entities per process (each for one task queue).
Example skeleton:

import asyncio
from temporalio.worker import Worker

async def run_workers(client, workflows, activities, task_queues, **worker_opts):
    workers = [
        Worker(client, task_queue=tq, workflows=workflows, activities=activities, **worker_opts)
        for tq in task_queues
    ]
    await asyncio.gather(*(w.run() for w in workers))


Tuning knobs (real ones, from Worker API)
Worker exposes controls like max_cached_workflows, max_concurrent_workflow_tasks, max_concurrent_activities, and per-second rate limits (max_activities_per_second, max_task_queue_activities_per_second).
Also, Temporal recommends poller autoscaling rather than manually tuning pollers.

Replay/sticky cache monitoring
Keep an eye on sticky cache eviction/pressure and schedule-to-start latency; Temporal documents specific metrics like forced evictions and sticky cache size.

MEDIUM
7) Tenant-safe “context contract” for all activities + queue fairness weighting by plan

Issue / risk
As you add workflows, the biggest real-world multi-tenant failure becomes “someone forgot to pass tenant_id/schema into an activity” (or passed the wrong one).

Why it matters
Temporal won’t protect you here; your code must. Namespaces isolate Temporal state, but your activities touch shared infrastructure.

Concrete pattern

Every tenant-scoped activity input includes {tenant_id, schema_name} (or a single TenantCtx)

Routing uses tenant_id for:

task queue shard selection

fairness key

(optional) namespace shard selection

Then you can map plans to fairness weights:

Free: 1

Pro: 3

Enterprise: 10
and pass fairness_weight via Priority.
This gives you “soft isolation” and fair scheduling without 1 namespace per tenant.

8) Visibility strategy: use Search Attributes carefully (and safely)

Search Attributes are great for operational queries and dashboards, but they are not encrypted, so don’t store PII there.
For tenant isolation/ops, tenant_id is fine.

In modern SDKs you can upsert search attributes over time (and they carry over across Continue-As-New).
Best practice is using typed keys (SDK support has improved; see SDK changelog).

9) Versioning and safe deployments (especially with entity workflows)

You’ll need safe evolution because entity workflows can be long-running.

Two pragmatic layers:

Use code-based version guards in workflow logic where you change determinism-critical behavior.

Adopt Worker Versioning (Build IDs) once you’re ready; Temporal documents worker versioning as a feature (noting preview/requirements depending on server version).

Self-hosted vs Temporal Cloud recommendations (multi-tenant isolation angle)

Temporal Cloud: APS/capacity is managed with per-namespace limits (and you request increases).
If you truly expect extreme load, you’ll likely end up with namespace sharding (e.g., prod-a, prod-b, …) to spread capacity and reduce blast radius.

Self-hosted: more freedom to create namespaces/queues and tune server configs, including task queue fairness configuration.
Still: too many namespaces has operational overhead; I’d shard tenants across a fixed number of namespaces rather than 1-per-tenant.

Pragmatic multi-tenant isolation model

Default: 1 namespace per environment, queue sharding + fairness keys

Enterprise/high-noise tenants: move to dedicated namespace (or dedicated namespace shard)

If you do namespace sharding and need cross-namespace orchestration later, Nexus is designed for connecting Temporal apps across isolated boundaries.

Migration plan (safe, incremental)

Namespace correctness first

Connect using settings.temporal_namespace everywhere (API + worker).

Introduce routing layer

Add routing.py, default shards=1 initially so behavior stays same.

Add new task queues + workers

Stand up worker deployments for saas.provisioning.00.., keep old worker running temporarily.

Flip workflow starts

Start routing new provisioning workflows to the new queues.

Roll out entity workflow template

Build new entity workflows using Updates/Queries + Continue-As-New guardrails (history-safe).

Enable fairness (optional, but recommended)

Start passing Priority(fairness_key=tenant_id) in starts/activities.

Configure task queue fairness defaults server-side.

Scale out

Increase shard count and worker replicas based on schedule-to-start latency and cache/replay metrics.

New tests + monitoring you should add

Tests

Workflow routing unit tests:

stable shard mapping

expected queue names

fairness priority assigned correctly

Integration test (Temporal test server or dev cluster):

start N provisioning workflows across many tenant_ids

assert they land on the expected queues (via worker logs/visibility)

Entity workflow history test:

submit many updates

assert Continue-As-New happens before warning thresholds

Monitoring

Alerts on:

task schedule-to-start latency (per queue shard)

worker forced sticky cache evictions (replay pressure)

APS utilization (Cloud)

workflows approaching history thresholds (log get_current_history_length() periodically for long-lived workflows)
