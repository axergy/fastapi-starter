"""
User Onboarding Workflow.

Onboard new user:
1. Create Stripe customer
2. Send welcome email

If step 1 succeeds but step 2 fails, Temporal only retries step 2.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.app.temporal.activities import (
        CreateStripeCustomerInput,
        CreateStripeCustomerOutput,
        SendEmailInput,
        create_stripe_customer,
        send_welcome_email,
    )


@workflow.defn
class UserOnboardingWorkflow:
    """
    Onboard new user:
    1. Create Stripe customer
    2. Send welcome email

    If step 1 succeeds but step 2 fails, Temporal only retries step 2.
    """

    @workflow.run
    async def run(self, user_email: str, user_name: str, tenant_id: str) -> str:
        stripe_result: CreateStripeCustomerOutput = await workflow.execute_activity(
            create_stripe_customer,
            CreateStripeCustomerInput(
                email=user_email,
                name=user_name,
                tenant_id=tenant_id,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
            ),
        )

        workflow.logger.info(f"Created Stripe customer: {stripe_result.stripe_customer_id}")

        await workflow.execute_activity(
            send_welcome_email,
            SendEmailInput(
                to=user_email,
                subject="Welcome!",
                body=f"Hello {user_name}, welcome to our platform!",
            ),
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                maximum_attempts=5,
                initial_interval=timedelta(seconds=2),
            ),
        )

        return stripe_result.stripe_customer_id
