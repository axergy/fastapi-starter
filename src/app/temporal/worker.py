"""
Temporal Worker - Separate process from API.

Run with:
    uv run python -m src.app.temporal.worker                  # Development mode (all workloads)
    uv run python -m src.app.temporal.worker --workload tenant # Tenant workloads only
    uv run python -m src.app.temporal.worker --workload jobs   # Jobs workloads only
"""

import argparse
import asyncio
from collections.abc import Sequence

import uvicorn
from fastapi import FastAPI
from temporalio.client import Client
from temporalio.worker import Worker

from src.app.core.config import get_settings
from src.app.core.logging import get_logger, setup_logging
from src.app.temporal.activities import (
    cleanup_email_verification_tokens,
    cleanup_expired_invites,
    cleanup_refresh_tokens,
    create_admin_membership,
    create_stripe_customer,
    dispose_sync_engine,
    drop_tenant_schema,
    get_tenant_info,
    run_tenant_migrations,
    send_welcome_email,
    soft_delete_tenant,
    update_tenant_status,
    update_workflow_execution_status,
)
from src.app.temporal.routing import QueueKind, task_queue_name
from src.app.temporal.workflows import (
    TenantDeletionWorkflow,
    TenantProvisioningWorkflow,
    TokenCleanupWorkflow,
    UserOnboardingWorkflow,
)

logger = get_logger(__name__)

WORKER_HEALTH_PORT = 8001


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for worker workload selection."""
    parser = argparse.ArgumentParser(description="Temporal worker")
    parser.add_argument(
        "--workload",
        choices=["tenant", "jobs", "all"],
        default="all",
        help="Worker workload type (default: all for development mode)",
    )
    return parser.parse_args()


async def create_worker(
    client: Client,
    task_queue: str,
    workflows: Sequence[type],
    activities: Sequence[object],  # type: ignore[type-arg]
    *,
    max_concurrent_activities: int = 100,
    max_concurrent_workflow_tasks: int = 100,
) -> Worker:
    """Create a worker with tuned settings.

    Args:
        client: Temporal client
        task_queue: Task queue name
        workflows: List of workflow classes
        activities: List of activity functions
        max_concurrent_activities: Max concurrent activity executions
        max_concurrent_workflow_tasks: Max concurrent workflow task executions

    Returns:
        Configured Worker instance
    """
    return Worker(
        client,
        task_queue=task_queue,
        workflows=list(workflows),
        activities=list(activities),  # type: ignore[arg-type]
        max_concurrent_activities=max_concurrent_activities,
        max_concurrent_workflow_tasks=max_concurrent_workflow_tasks,
    )


async def run_tenant_workers(client: Client) -> None:
    """Run workers for tenant queues (all tenant-scoped workflows).

    Creates one worker per shard to handle tenant provisioning, deletion,
    and user onboarding workflows. Tuned for lower concurrency and longer
    timeouts due to heavy database operations.
    """
    settings = get_settings()
    workers = []

    # Tenant activities
    tenant_activities = [
        create_admin_membership,
        create_stripe_customer,
        drop_tenant_schema,
        get_tenant_info,
        run_tenant_migrations,
        send_welcome_email,
        soft_delete_tenant,
        update_tenant_status,
        update_workflow_execution_status,
    ]

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
            activities=tenant_activities,
            max_concurrent_activities=20,
            max_concurrent_workflow_tasks=20,
        )
        workers.append(worker)
        logger.info(f"Created tenant worker for queue: {tq}")

    logger.info(f"Starting {len(workers)} tenant worker(s)")
    await asyncio.gather(*(w.run() for w in workers))


async def run_jobs_workers(client: Client) -> None:
    """Run workers for job queues (system-wide background tasks).

    Handles cleanup jobs and scheduled tasks. Tuned for higher concurrency
    as these are typically quick operations without heavy database work.
    """
    settings = get_settings()
    tq = task_queue_name(settings.temporal_queue_prefix, QueueKind.JOBS, 0)

    # Jobs activities
    jobs_activities = [
        cleanup_email_verification_tokens,
        cleanup_expired_invites,
        cleanup_refresh_tokens,
    ]

    worker = await create_worker(
        client,
        tq,
        workflows=[TokenCleanupWorkflow],
        activities=jobs_activities,
        max_concurrent_activities=50,
        max_concurrent_workflow_tasks=50,
    )
    logger.info(f"Starting jobs worker on queue: {tq}")
    await worker.run()


async def run_health_server(
    workload: str,
    task_queues: list[str],
    port: int = WORKER_HEALTH_PORT,
) -> None:
    """Run a lightweight health server for K8s probes.

    Args:
        workload: Workload type (tenant, jobs, all)
        task_queues: List of task queues being polled
        port: Port to listen on
    """
    health_app = FastAPI(title="Temporal Worker Health")

    @health_app.get("/health")
    async def health() -> dict[str, str | list[str]]:
        return {
            "status": "healthy",
            "service": "temporal-worker",
            "workload": workload,
            "task_queues": task_queues,
        }

    @health_app.get("/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready"}

    config = uvicorn.Config(
        health_app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    logger.info(f"Starting health server on port {port} (workload: {workload})")
    await server.serve()


async def main() -> None:
    """Main entry point for the Temporal worker.

    Supports three modes:
    - tenant: Polls tenant queues only (production deployment)
    - jobs: Polls jobs queue only (production deployment)
    - all: Polls all queues in one process (development mode)
    """
    args = parse_args()
    settings = get_settings()
    setup_logging(settings.debug)

    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    # Build task queue list for health reporting
    task_queues = []
    if args.workload in ["tenant", "all"]:
        for shard in range(settings.temporal_queue_shards):
            tq = task_queue_name(settings.temporal_queue_prefix, QueueKind.TENANT, shard)
            task_queues.append(tq)
    if args.workload in ["jobs", "all"]:
        tq = task_queue_name(settings.temporal_queue_prefix, QueueKind.JOBS, 0)
        task_queues.append(tq)

    logger.info(f"Starting worker with workload: {args.workload}")
    logger.info(f"Polling task queues: {', '.join(task_queues)}")

    try:
        # Start health server alongside worker(s)
        health_task = asyncio.create_task(run_health_server(args.workload, task_queues))

        if args.workload == "tenant":
            await run_tenant_workers(client)
        elif args.workload == "jobs":
            await run_jobs_workers(client)
        elif args.workload == "all":
            # Development mode: run all workers in one process
            await asyncio.gather(
                run_tenant_workers(client),
                run_jobs_workers(client),
            )

        # Wait for health server to finish (should never happen)
        await health_task
    finally:
        dispose_sync_engine()


if __name__ == "__main__":
    asyncio.run(main())
