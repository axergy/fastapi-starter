Where you are now (quick read)

You’re already very close to production-grade: schema quoting/validation is solid, Alembic is much safer than most multi-tenant starters, and the Temporal workflow/compensation story is a strong foundation.

Top highest-impact improvements I’d make to get to “gold standard”:

Fix a real isolation footgun: pooled connections + search_path switching + asyncpg/driver statement caches can cause cross-tenant prepared statement reuse unless you explicitly disable statement caching. Your engine config doesn’t currently do that.

code

Close two public attack surfaces: /tenants create + status endpoints appear unauthenticated, enabling tenant enumeration and provisioning/DDoS abuse.

code

Provisioning is not fully idempotent/observable yet: you have workflow_executions, but it’s not enforced unique and isn’t updated by the workflow itself; status is derived from Temporal calls.

code

Public migrations are not forced into public schema: your Alembic env only sets search_path for tenant-tagged runs, not for public runs. Combined with unqualified op.create_table(...) in 001, this is a correctness risk.

code



code

Fix a hard mismatch: tenants.slug is created with length 50 in 001, but your model + constraints assume 56. That will bite immediately in production.

code



code



code

Below is a prioritized, production-hardening punch list with concrete diffs.

Critical
1) Bulletproof tenant isolation: disable statement caching with schema switching

Issue / risk
You are using pooled connections (pool_size, max_overflow) with session-level SET search_path switching for tenant sessions.

code



code


With asyncpg (your URL is +asyncpg throughout the codebase), this pattern is vulnerable to prepared statement / statement cache reuse across schema changes unless you explicitly disable the driver/dialect statement cache. The result can be “query compiled/prepared against tenant A gets executed later while tenant B is on the connection”.

Why it matters
This is a tenant data isolation class risk (worst case: cross-tenant read/write). Even if it’s intermittent, it’s unacceptable in a multi-tenant starter.

Concrete change (minimal, high-signal)

src/app/core/config.py – add a setting (default safe):

diff --git a/src/app/core/config.py b/src/app/core/config.py
@@
 class Settings(BaseSettings):
@@
     database_url: str
+    # IMPORTANT for schema-per-tenant via search_path:
+    # Disable asyncpg statement cache to prevent cross-tenant prepared statement reuse.
+    database_statement_cache_size: int = 0


src/app/core/db/engine.py – pass it to connect args and add pool_pre_ping:

diff --git a/src/app/core/db/engine.py b/src/app/core/db/engine.py
@@
 def get_engine() -> AsyncEngine:
@@
-        connect_args = {}
+        connect_args: dict[str, object] = {}
+
+        # Critical: avoid cached prepared statements when switching search_path per request
+        # (schema-per-tenant Lobby Pattern).
+        connect_args["statement_cache_size"] = settings.database_statement_cache_size
@@
         _engine = create_async_engine(
             settings.database_url,
             echo=settings.debug,
             pool_size=settings.database_pool_size,
             max_overflow=settings.database_max_overflow,
+            pool_pre_ping=True,
             connect_args=connect_args,
         )


If you want belt + suspenders, I’d also add a “strict reset” mode later (e.g., DEALLOCATE ALL on checkout/checkin), but disabling statement caching is the core fix.

2) Fix rate-limit bypass & unbounded-cardinality buckets

Issue / risk
Your rate-limit key function includes attacker-controlled X-Tenant-ID in the key: ip:tenant_slug.

code


That allows:

Trivial bypass: change the header each request → new bucket

Memory blow-up in in-memory fallback (tons of unique keys)

Why it matters
This is a DDoS / brute-force amplification vector that attackers will find fast.

Concrete change
Key rate limits by IP only. If you want per-tenant quotas, do it only with validated tenant identity (post-lookup) in a separate limiter layer—not by raw header.

diff --git a/src/app/core/rate_limit.py b/src/app/core/rate_limit.py
@@
 def get_rate_limit_key(request: Request) -> str:
@@
-    tenant_id = request.headers.get("X-Tenant-ID", "")
-    if tenant_id:
-        return f"{ip}:{tenant_id}"
-    return ip
+    # Key only by IP. Anything derived from headers is attacker-controlled here and
+    # enables trivial bypass + unbounded key cardinality.
+    return ip


This will require updating your tests that expect ip:tenant (they currently do).

code

3) Lock down /tenants create + status endpoints (currently public)

Issue / risk
The POST /tenants endpoint appears to have no auth dependency (no current_user).

code


Same file shows a public GET /tenants/status/{tenant_slug} pattern.

code

Why it matters

Anyone can spam tenant provisioning workflows (cost + noise)

Tenant enumeration (“does this slug exist?”)

Leaks operational status and temporal errors

Concrete change

Make /tenants management admin-only

Replace public status polling by unguessable workflow_id (UUID-based), rate-limited

diff --git a/src/app/api/v1/tenants.py b/src/app/api/v1/tenants.py
@@
-from src.app.api.dependencies.auth import AuthenticatedUser
+from src.app.api.dependencies.auth import AuthenticatedUser, SuperUser
 from src.app.core.rate_limit import limiter
@@
 @router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
 async def create_tenant(
     tenant_data: TenantCreate,
     tenant_service: TenantServiceDep,
+    current_user: SuperUser,
 ) -> TenantResponse:
@@
-@router.get("/status/{tenant_slug}", response_model=TenantStatusResponse)
-async def get_tenant_status(
-    tenant_slug: str, tenant_service: TenantServiceDep
-) -> TenantStatusResponse:
+@router.get("/status/{tenant_slug}", response_model=TenantStatusResponse)
+async def get_tenant_status(
+    tenant_slug: str,
+    tenant_service: TenantServiceDep,
+    current_user: SuperUser,
+) -> TenantStatusResponse:
     """Admin-only tenant status by slug."""
     return await tenant_service.get_tenant_status(tenant_slug)


Then add a new public polling endpoint that uses workflow_id (see provisioning section below), and slap a tight rate limit on it (e.g., 30/minute).

4) Fix Alembic env: force search_path=public and fix tag handling

Issue / risk

Your Alembic env only sets search_path when a schema tag is provided, not for public runs.

code

do_run_migrations uses if schema: (truthy), but include_object treats “tag argument present” as tenant mode even if the string is empty. That mismatch can cause confusing behavior.

code



code

Your 001 migration creates tables without explicit schema (relies on search_path).

code

Why it matters
This is a correctness/safety issue: under nonstandard search_path (common with $user schemas), you can create tables or alembic_version in the wrong schema.

Concrete change (full replacement of do_run_migrations + improved include filter)

diff --git a/src/alembic/env.py b/src/alembic/env.py
@@
 def include_object(object, name, type_, reflected, compare_to):
@@
-    if type_ == "table":
-        is_tenant_migration = context.get_tag_argument() is not None
-        object_schema = getattr(object, "schema", None)
-
-        if is_tenant_migration:
-            # Tenant migrations should ONLY touch tables WITHOUT 'public' schema
-            return object_schema != "public"
-        else:
-            # Public migrations should ONLY touch tables WITH 'public' schema
-            return object_schema == "public"
+    # Filter objects to prevent cross-schema contamination in autogenerate.
+    schema_tag = context.get_tag_argument()
+    is_tenant_migration = schema_tag is not None
+    if is_tenant_migration:
+        validate_schema_name(schema_tag)
+        allowed_schema = schema_tag
+    else:
+        allowed_schema = "public"
+
+    # Normalize schema extraction for non-table objects (indexes/constraints).
+    object_schema = getattr(object, "schema", None)
+    if object_schema is None and hasattr(object, "table"):
+        object_schema = getattr(object.table, "schema", None)
+
+    if type_ in {
+        "table",
+        "index",
+        "unique_constraint",
+        "foreign_key_constraint",
+        "check_constraint",
+        "primary_key_constraint",
+    }:
+        return object_schema == allowed_schema
@@
 def do_run_migrations(connection, schema: str | None = None) -> None:
     """Run migrations for a specific schema."""
-    if schema:
+    if schema is not None:
         # Validate schema name before any SQL execution
         validate_schema_name(schema)
@@
         connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}"))
         connection.execute(text(f"SET search_path TO {quoted_schema}"))
         connection.commit()
         context.configure(
@@
             include_object=include_object,
         )
     else:
+        # Force public schema for public migrations (do not rely on DB/user defaults)
+        connection.execute(text("SET search_path TO public"))
+        connection.commit()
         context.configure(
             connection=connection,
             target_metadata=target_metadata,
+            version_table_schema="public",
             compare_type=True,
             include_object=include_object,
         )


This directly addresses the public-schema correctness gap shown in your current env.py.

code

5) Fix tenant slug max-length mismatch (DB is 50, code assumes 56)

Issue / risk

DB created in 001 has slug length 50.

code

Code/model expects 56, and you add constraints assuming 56.

code



code

Why it matters
Provisioning will fail unexpectedly when a valid slug (<=56) exceeds column length (50). This is a hard production defect.

Concrete change
Add an Alembic migration after 012 to alter the column type length.

Create src/alembic/versions/013_fix_tenants_slug_length_and_workflow_uniques.py:

"""
Fix tenants.slug length and add workflow_executions uniqueness

Revision ID: 013
Revises: 012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if context.get_tag_argument():
        return

    # Align DB column length with code + constraints (56)
    op.alter_column(
        "tenants",
        "slug",
        existing_type=sa.String(length=50),
        type_=sa.String(length=56),
        existing_nullable=False,
    )

    # Enforce uniqueness of workflow_id (code assumes 1 row per workflow)
    op.create_unique_constraint(
        "uq_workflow_executions_workflow_id",
        "workflow_executions",
        ["workflow_id"],
        schema="public",
    )


def downgrade() -> None:
    if context.get_tag_argument():
        return

    op.drop_constraint(
        "uq_workflow_executions_workflow_id",
        "workflow_executions",
        type_="unique",
        schema="public",
    )

    op.alter_column(
        "tenants",
        "slug",
        existing_type=sa.String(length=56),
        type_=sa.String(length=50),
        existing_nullable=False,
    )


The workflow uniqueness addresses the current “index only” situation.

code

High
6) Make tenant provisioning atomic-ish, idempotent, and observable via workflow_executions

Issue / risk

TenantService.create_tenant creates workflow_exec and starts workflow, but the workflow itself does not update the record lifecycle; the public status endpoint queries Temporal.

code



code

Registration flow starts Temporal but does not create a workflow_executions row, so DB observability is inconsistent.

code

workflow_id is currently deterministic from slug (tenant-provision-{tenant_slug}) which is guessable.

code

Why it matters

Idempotency: repeated calls can start duplicate workflows or leave partial state

Observability: ops teams need a DB record of “pending/running/failed/completed”

Security: guessable IDs enable public status scraping

Concrete changes (incremental path)

Step A — standardize workflow_id to UUID-based (tenant_id) and create workflow_executions everywhere

In both TenantService + RegistrationService:

Use: workflow_id = f"tenant-provision-{tenant.id}" (unguessable UUID)

Always create a WorkflowExecution(status="pending") row in the same DB transaction that creates the tenant

In src/app/services/tenant_service.py:

diff --git a/src/app/services/tenant_service.py b/src/app/services/tenant_service.py
@@
-    def _workflow_id_for_tenant(self, slug: str) -> str:
-        return f"tenant-provision-{slug}"
+    def _workflow_id_for_tenant(self, tenant_id: UUID) -> str:
+        return f"tenant-provision-{tenant_id}"
@@
-        tenant = await self.tenant_repo.create(...)
-        await self.session.commit()
-        await self.session.refresh(tenant)
+        async with self.session.begin():
+            tenant = await self.tenant_repo.create(...)
+            workflow_id = self._workflow_id_for_tenant(tenant.id)
+            self.session.add(
+                WorkflowExecution(
+                    workflow_id=workflow_id,
+                    workflow_type="tenant_provisioning",
+                    entity_type="tenant",
+                    entity_id=tenant.id,
+                    status="pending",
+                )
+            )
@@
-        workflow_id = self._workflow_id_for_tenant(tenant.slug)
+        workflow_id = self._workflow_id_for_tenant(tenant.id)


(You already have the WorkflowExecution model/repo.

code

 )

Step B — have the workflow update DB state (running/completed/failed)

Add a Temporal activity to update the workflow execution:

src/app/temporal/activities.py:

from dataclasses import dataclass
from temporalio import activity

@dataclass
class UpdateWorkflowExecutionInput:
    workflow_id: str
    status: str
    error_message: str | None = None

@activity.defn
async def update_workflow_execution(input: UpdateWorkflowExecutionInput) -> None:
    async with get_public_session() as session:
        repo = WorkflowExecutionRepository(session)
        we = await repo.get_by_workflow_id(input.workflow_id)
        if not we:
            activity.logger.warning("workflow_execution_not_found", workflow_id=input.workflow_id)
            return

        we.status = input.status
        if input.status == "running" and we.started_at is None:
            we.started_at = utc_now()
        if input.status in {"completed", "failed"}:
            we.completed_at = utc_now()
        we.error_message = input.error_message
        await session.commit()


Then in TenantProvisioningWorkflow, call it:

first thing: mark running

end: mark completed

except: mark failed

This complements your existing saga/compensation flow.

code

Step C — public polling endpoint should read DB first, Temporal second

This gives graceful degradation if Temporal is flaky:

If DB shows completed/failed → return immediately

If pending/running → optionally query Temporal handle; if Temporal down, still return “pending/running” without erroring

7) Tenant status transitions should update is_active + store failure reason

Issue / risk
update_tenant_status only updates tenant.status today.

code


So a failed tenant can remain is_active=true and look “valid” to other flows.

Why it matters

Security/logic: “failed” tenants should not authenticate / mint tokens

Ops: you want a persisted error reason for debugging

Concrete change

Add last_provision_error + status_updated_at columns (optional but high value)

Update is_active based on status (ready => true, failed/deleted => false)

Example activity change (minimal, no schema change):

diff --git a/src/app/temporal/activities.py b/src/app/temporal/activities.py
@@
 async def update_tenant_status(input: UpdateTenantStatusInput) -> None:
@@
-        tenant.status = input.status
+        tenant.status = input.status
+        if input.status == "ready":
+            tenant.is_active = True
+        elif input.status in {"failed", "deleted"}:
+            tenant.is_active = False
         await session.commit()

8) Separate DB privileges (runtime vs migrator/provisioner)

Issue / risk
Right now the same DB URL appears to be used for:

normal API operations

Alembic DDL migrations (env.py uses settings.database_url)

code

provisioning schema creation (Alembic tenant-tag path creates schema)

code

Why it matters
If an attacker ever gets SQL injection or any arbitrary-SQL primitive in the API role, DDL privileges turn that into:

create malicious functions/types

drop schemas/tables

persistence

Concrete change
Add a second URL for migrations and use it in Alembic + provisioning-only code paths.

src/app/core/config.py:

@@
 class Settings(BaseSettings):
     database_url: str
+    database_migrations_url: str | None = None


src/alembic/env.py:

 def get_url() -> str:
     """Get sync database URL (convert asyncpg to psycopg2)."""
-    url = get_settings().database_url
+    settings = get_settings()
+    url = settings.database_migrations_url or settings.database_url
     return url.replace("+asyncpg", "")


src/app/core/db/migrations.py should also prefer database_migrations_url for alembic_cfg.set_main_option("sqlalchemy.url", ...).

code

Recommended privilege baseline (no per-tenant roles yet)

app_runtime: CRUD only, no CREATE/ALTER/DROP

app_migrator: owns schemas/tables and can run Alembic / provisioning DDL

Then your provisioning step should GRANT USAGE + table privileges on the tenant schema to app_runtime.

(Per-tenant DB roles are optional; see “Medium” for pros/cons.)

Medium
9) workflow_executions.workflow_id should be unique in the model too

You currently create only a non-unique index.

code


After adding the DB constraint (migration above), update the model:

diff --git a/src/app/models/public/workflow.py b/src/app/models/public/workflow.py
@@
-    workflow_id: str = Field(sa_column=Column(String(255), nullable=False, index=True))
+    workflow_id: str = Field(sa_column=Column(String(255), nullable=False, unique=True, index=True))

10) Per-tenant DB roles: pros/cons + incremental path

Pros

Strongest isolation if you also grant each tenant role access only to that schema

Lets you revoke/suspend a tenant at the DB layer

Cons

Operational complexity: role creation, grants, rotation, pool management

Connection pool can’t easily multiplex roles unless you SET ROLE per checkout (doable, but more moving parts)

Incremental path

Mandatory: split runtime vs migrator role (above)

Add optional SET ROLE tenant_role in get_tenant_session after validation

Only then consider true per-tenant ownership/grants

11) Performance: auditing should be “cheap by default”

Your audit logging currently commits its own transaction per event (good isolation), but it’s still synchronous on the request path. If you expect volume, add a config that allows:

“sync write” (current)

“async emit” (queue to Redis/Temporal activity, write later)

“sampled” for noisy endpoints

(Your current DB table/index design looks reasonable.

code

 )

12) Testing: add lifecycle integration + property-based validators

Add integration tests

tenant registration → workflow_executions row created → provisioning completes → tenant status ready and schema exists

provisioning failure path → tenant status failed, is_active=false, schema dropped (your workflow already compensates)

code

Property-based tests

slug/schema validators: generate random strings and ensure reject lists hold (forbidden patterns, max lengths, double underscores, uppercase, etc.)

Polish (still worth doing)
13) Fix OpenAPI examples that contradict your slug rules

Some examples show hyphenated slugs (acme-corp) while your validators and constraints are underscore-based.

code


This causes immediate developer confusion.

Recommended next-step monitoring hooks

Metrics counters

tenant_provision_started_total

tenant_provision_failed_total

tenant_provision_duration_seconds (histogram)

Alert conditions

“failed provisioning in last 15m > N”

“pending provisioning older than X minutes” (query workflow_executions where status in pending/running and created_at < now()-interval)

Log correlation

Add workflow_id, tenant_id, request_id into structured logs for provisioning paths (you already carry request context; just propagate workflow_id consistently)
