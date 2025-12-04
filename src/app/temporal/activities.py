"""
Temporal Activities - Fine-grained, idempotent operations.

Activities should be:
1. Idempotent - Safe to retry
2. Fine-grained - Do one thing well
3. Side-effect aware - External calls go here, not in workflows
"""

from dataclasses import dataclass

from temporalio import activity


@dataclass
class SendEmailInput:
    to: str
    subject: str
    body: str


@activity.defn
async def send_welcome_email(input: SendEmailInput) -> bool:
    """
    Send welcome email to new user.

    In production, integrate with email service (SendGrid, SES, etc.)
    """
    activity.logger.info(f"Sending welcome email to {input.to}")
    # TODO: Integrate with actual email service
    # await email_client.send(to=input.to, subject=input.subject, body=input.body)
    return True


@dataclass
class CreateStripeCustomerInput:
    email: str
    name: str
    tenant_id: str


@dataclass
class CreateStripeCustomerOutput:
    stripe_customer_id: str


@activity.defn
async def create_stripe_customer(
    input: CreateStripeCustomerInput,
) -> CreateStripeCustomerOutput:
    """
    Create Stripe customer for new user.

    IMPORTANT: Must be idempotent. Use Stripe's idempotency keys.
    """
    activity.logger.info(f"Creating Stripe customer for {input.email}")
    # TODO: Integrate with Stripe
    # customer = await stripe.Customer.create(
    #     email=input.email,
    #     name=input.name,
    #     metadata={"tenant_id": input.tenant_id},
    #     idempotency_key=f"customer_{input.tenant_id}_{input.email}",
    # )
    return CreateStripeCustomerOutput(stripe_customer_id="cus_placeholder")
