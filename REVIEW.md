2) Tenant schema support exists… but isn’t wired into API usage

You have get_tenant_session() implemented correctly.

code


But your general DBSession dependency uses get_public_session() only.

code


And tenant resolution pulls tenant info from the public schema (that part is correct).

code

What’s missing for a “multi-tenant starter” is the standard, obvious dependency like:

TenantDBSession (tenant schema)

at least one example tenant-scoped model + CRUD endpoint to prove isolation end-to-end

Right now your tenant-schema packages are basically placeholders.

code

What I’d add:

# src/app/api/deps.py (or api/dependencies/db.py)
from typing import AsyncGenerator, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from src.app.api.dependencies.tenant import ValidatedTenant
from src.app.core.db.session import get_tenant_session

async def get_tenant_db_session(
    tenant: ValidatedTenant,
) -> AsyncGenerator[AsyncSession, None]:
    async with get_tenant_session(tenant.schema_name) as session:
        yield session

TenantDBSession = Annotated[AsyncSession, Depends(get_tenant_db_session)]


Then create a tiny tenant-scoped resource like Project or Note (tenant schema), with GET/POST, and a test verifying:

tenant A can’t see tenant B’s rows

even if IDs are guessed

That makes the repo instantly trustworthy as a “starter”.

3) Slug format rules conflict with your own API examples

Your schema says “underscores only, no hyphens”.

code


You also have tests explicitly rejecting hyphens.

code


…but your OpenAPI examples show slugs like "acme-corp" and "beta-industries".

code

This will confuse people immediately.

Pick one:

If you want “normal SaaS slugs”, allow hyphens in TENANT_SLUG_REGEX and in schema validation.

If you want underscores only (fine!), update all examples/docs to match.

Related: the header is called X-Tenant-ID but it’s actually a slug in practice.

code


Consider renaming to X-Tenant-Slug (or support both slug + UUID).

4) “Users can only belong to one tenant” is a product decision baked into API

Your invite accept endpoint explicitly states you reject if email already exists.

code


That’s totally valid for some products, but it’s not typical for B2B SaaS where a user can belong to multiple tenants.

If this is meant to be a general starter, I’d make this behavior configurable or implement:

invite acceptance for existing logged-in user

membership join flow

tenant switching (token minted for chosen tenant)

Feature additions I’d recommend for the starter (prioritized)
Must-have (to make “multi-tenant starter” feel complete)

TenantDBSession dependency + tenant-scoped example CRUD (as described above)

code



code

Tenant resolution options:

header (already)

subdomain ({tenant}.api.com)

path prefix (/t/{slug}/...)

Tenant-aware background work examples: you’re routing Temporal queues by tenant already, but add one sample “tenant job” that uses tenant schema session inside an activity.

code

High value next

Per-tenant quotas + plan enforcement hooks (rate limit, workflow priority, max seats, etc.)

Tenant lookup caching (Redis TTL cache) to avoid hitting DB on every request for header → tenant resolution

code

API keys per tenant (service-to-service auth distinct from user JWTs)

Nice-to-have / polish

OpenTelemetry tracing with tenant_id, request_id, user_id attributes (your request context is already halfway there)

code

Consistent error response schema (typed error model everywhere)
