"""
Temporal Worker - Separate process from API.

Run with: uv run python -m src.app.temporal.worker
"""

import asyncio

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
)
from src.app.temporal.workflows import (
    TenantDeletionWorkflow,
    TenantProvisioningWorkflow,
    TokenCleanupWorkflow,
    UserOnboardingWorkflow,
)

logger = get_logger(__name__)

WORKER_HEALTH_PORT = 8001


async def run_health_server(task_queue: str, port: int = WORKER_HEALTH_PORT) -> None:
    """Run a lightweight health server for K8s probes."""
    health_app = FastAPI(title="Temporal Worker Health")

    @health_app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "healthy",
            "service": "temporal-worker",
            "task_queue": task_queue,
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
    logger.info(f"Starting health server on port {port}")
    await server.serve()


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.debug)

    client = await Client.connect(settings.temporal_host)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[
            UserOnboardingWorkflow,
            TenantProvisioningWorkflow,
            TenantDeletionWorkflow,
            TokenCleanupWorkflow,
        ],
        activities=[
            cleanup_email_verification_tokens,
            cleanup_expired_invites,
            cleanup_refresh_tokens,
            create_admin_membership,
            create_stripe_customer,
            drop_tenant_schema,
            get_tenant_info,
            run_tenant_migrations,
            send_welcome_email,
            soft_delete_tenant,
            update_tenant_status,
        ],
    )

    logger.info(f"Starting worker on queue: {settings.temporal_task_queue}")
    try:
        # Run worker and health server concurrently
        await asyncio.gather(
            worker.run(),
            run_health_server(settings.temporal_task_queue),
        )
    finally:
        dispose_sync_engine()


if __name__ == "__main__":
    asyncio.run(main())
