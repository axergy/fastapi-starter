"""Stripe integration activities."""

from dataclasses import dataclass

from temporalio import activity


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

    Idempotency: Uses Stripe's native idempotency key feature. All Stripe API
    POST requests accept an idempotency key parameter. If Stripe receives a
    request with the same idempotency key, it will return the cached result
    instead of creating a duplicate resource.

    The idempotency key should be deterministic and unique per customer:
        idempotency_key = f"customer_{tenant_id}_{email}"

    This ensures that if the activity is retried due to network failure or
    worker crash, no duplicate Stripe customers will be created.

    Implementation pattern:
        customer = await stripe.Customer.create(
            email=input.email,
            name=input.name,
            metadata={"tenant_id": input.tenant_id},
            idempotency_key=f"customer_{input.tenant_id}_{input.email}",
        )

    Note: Stripe stores idempotency keys for 24 hours, which is sufficient
    for Temporal's retry windows.

    Args:
        input: CreateStripeCustomerInput with email, name, and tenant_id

    Returns:
        CreateStripeCustomerOutput with the Stripe customer ID
    """
    activity.logger.info(f"Creating Stripe customer for {input.email}")
    # TODO: Integrate with Stripe (see docstring for idempotency pattern)
    return CreateStripeCustomerOutput(stripe_customer_id="cus_placeholder")
