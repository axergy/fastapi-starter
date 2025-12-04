"""
Temporal Worker - Separate process from API.

Run with: uv run python -m src.app.temporal.worker
"""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from src.app.core.config import get_settings
from src.app.temporal.activities import (
    create_stripe_customer,
    create_tenant_record,
    run_tenant_migrations,
    send_welcome_email,
    update_tenant_status,
)
from src.app.temporal.workflows import TenantProvisioningWorkflow, UserOnboardingWorkflow


async def main() -> None:
    settings = get_settings()

    client = await Client.connect(settings.temporal_host)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[UserOnboardingWorkflow, TenantProvisioningWorkflow],
        activities=[
            create_stripe_customer,
            send_welcome_email,
            create_tenant_record,
            run_tenant_migrations,
            update_tenant_status,
        ],
    )

    print(f"Starting worker on queue: {settings.temporal_task_queue}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
