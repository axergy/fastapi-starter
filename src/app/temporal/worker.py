"""
Temporal Worker - Separate process from API.

Run with: uv run python -m src.app.temporal.worker
"""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from src.app.core.config import get_settings
from src.app.core.logging import get_logger, setup_logging
from src.app.temporal.activities import (
    create_admin_membership,
    create_stripe_customer,
    dispose_sync_engine,
    run_tenant_migrations,
    send_welcome_email,
    update_tenant_status,
)
from src.app.temporal.workflows import TenantProvisioningWorkflow, UserOnboardingWorkflow

logger = get_logger(__name__)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.debug)

    client = await Client.connect(settings.temporal_host)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[UserOnboardingWorkflow, TenantProvisioningWorkflow],
        activities=[
            create_admin_membership,
            create_stripe_customer,
            send_welcome_email,
            run_tenant_migrations,
            update_tenant_status,
        ],
    )

    logger.info(f"Starting worker on queue: {settings.temporal_task_queue}")
    try:
        await worker.run()
    finally:
        dispose_sync_engine()


if __name__ == "__main__":
    asyncio.run(main())
