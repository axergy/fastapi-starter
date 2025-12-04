Markdown

# 🚀 FastAPI Enterprise SaaS Starter (SOTA Edition)

A production-ready, multi-tenant FastAPI boilerplate designed for high-performance SaaS applications. This starter kit implements **Schema-per-Tenant** isolation, durable background workflows with **Temporal**, and modern Python tooling with **uv**.

## 🛠 Tech Stack & Architecture

### Core Frameworks
* **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Async, Type-safe)
* **ORM**: [SQLModel](https://sqlmodel.tiangolo.com/) (SQLAlchemy + Pydantic v2)
* **Package Manager**: [uv](https://github.com/astral-sh/uv) (Rust-based, 10-100x faster than Pip/Poetry)
* **Database**: PostgreSQL 16+ (Required for Schema isolation)

### Multi-Tenancy (The "Hard" Part)
* **Strategy**: **Schema-per-Tenant**.
    * *Public Schema*: Holds shared data (Tenants table, Plans, System Config).
    * *Tenant Schemas*: Each tenant gets a dedicated Postgres schema (e.g., `tenant_acme`, `tenant_xyz`).
* **Isolation**: Middleware intercepts `X-Tenant-ID` (or subdomain), and the DB session automatically executes `SET search_path TO tenant_x, public`. Data leakage is architecturally impossible at the query level.

### Background Workflows & Reliability
* **Orchestrator**: [Temporal.io](https://temporal.io/). Replaces standard Celery/Redis queues.
    * *Why?* Durable execution. If the worker crashes mid-process (e.g., "Step 2 of 5"), Temporal resumes exactly at Step 2 upon restart. No state loss.
* **Monitoring**: [Sentry](https://sentry.io/) for error tracking and performance tracing.

### Security
* **Auth**: JWT (Access + Refresh Tokens) with sliding sessions.
* **Hashing**: Argon2id (via `passlib`).
* **Validation**: Pydantic v2 Strict Mode.

---

## 📂 Project Structure (MVC / Service-Layer Pattern)

We move away from the flat `main.py` style to a strict separation of concerns.

```text
├── .github/                # CI/CD pipelines
├── deploy/                 # Docker & K8s configs
├── src/
│   ├── app/
│   │   ├── api/            # [VIEW/CONTROLLER] Routes & Request Handling
│   │   │   ├── v1/
│   │   │   │   ├── auth.py
│   │   │   │   ├── users.py
│   │   │   │   └── billing.py
│   │   │   └── dependencies.py # Tenant resolution, Current User
│   │   │
│   │   ├── core/           # Config, Security, Logging, Exceptions
│   │   │
│   │   ├── models/         # [MODEL] SQLModel Database Tables
│   │   │   ├── base.py     # TenantMixin (adds tenant_id context)
│   │   │   ├── tenant.py   # Public schema models
│   │   │   └── user.py     # Tenant schema models
│   │   │
│   │   ├── schemas/        # [VIEW MODEL] Pydantic DTOs (Request/Response)
│   │   │
│   │   ├── services/       # [CONTROLLER/LOGIC] Pure Business Logic
│   │   │   ├── auth_service.py
│   │   │   ├── user_service.py
│   │   │   └── tenant_ops.py
│   │   │
│   │   └── temporal/       # Background Workflows
│   │       ├── activities.py
│   │       ├── workflows.py
│   │       └── worker.py   # Separate entrypoint
│   │
│   ├── alembic/            # Migrations (Multi-tenant aware)
│   └── main.py             # App Entrypoint
│
├── tests/
├── compose.yml             # Full local stack (App, DB, Temporal, Sentry)
├── pyproject.toml          # uv dependency definition
└── uv.lock
⚡️ Quick Start
1. Prerequisites
Install uv (The future of Python packaging):

Bash

curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh
2. Install Dependencies
Bash

uv sync
3. Run Infrastructure (Docker Compose)
Spins up Postgres, Temporal Service, and Temporal Web UI.

Bash

docker compose up -d
4. Run the App (Dev Mode)
Bash

uv run fastapi dev src/app/main.py
5. Run the Temporal Worker
The worker handles background tasks (email sending, report generation) independently of the API.

Bash

uv run python -m src.app.temporal.worker
🔐 Key Features Breakdown
1. The Multi-Tenant Session
We do not create separate database connections for every tenant. Instead, we use a lightweight context switch.

Python

# src/app/core/db.py (Simplified)

def get_db(tenant_schema: str = Depends(get_current_tenant_schema)):
    """
    Dependency that yields a session configured for the specific tenant.
    """
    with engine.connect() as connection:
        # MAGIC HAPPENS HERE: Postgres switches context efficiently
        connection.execute(text(f"SET search_path TO {tenant_schema}, public"))

        with Session(connection) as session:
            yield session
2. Temporal Workflows (Instead of Celery)
We define workflows as code. This "User Onboarding" workflow is crash-proof.

Python

# src/app/temporal/workflows.py

@workflow.defn
class OnboardingWorkflow:
    @workflow.run
    async def run(self, user_email: str):
        # Step 1: Create Stripe Customer
        stripe_id = await workflow.execute_activity(
            create_stripe_customer,
            user_email,
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Step 2: Send Welcome Email
        await workflow.execute_activity(
            send_welcome_email,
            user_email,
            start_to_close_timeout=timedelta(seconds=5)
        )
3. Docker Multi-Stage Build with uv
We use uv in Docker for extremely fast builds and small images.

Dockerfile

# Dockerfile
FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
# Install dependencies into a virtual environment
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm
WORKDIR /app
# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Enable venv
ENV PATH="/app/.venv/bin:$PATH"
COPY src ./src

CMD ["fastapi", "run", "src/app/main.py", "--port", "80"]
🧪 Testing
We use pytest with a custom fixture that creates a temporary schema for each test function, ensuring complete isolation.

Bash

uv run pytest
📜 License
MIT


### Why this is "State of the Art"?

1.  **uv**: Most tutorials still use Poetry or Pip. `uv` is significantly faster and simplifies Docker builds (as shown in the Dockerfile snippet).
2.  **Schema-per-Tenant**: Row-level security (shared tables) is easier to start but harder to scale securely (one missed `WHERE` clause leaks data). Database-per-tenant is too expensive. Schema-per-tenant is the "Goldilocks" zone for B2B SaaS.
3.  **Temporal**: Celery is "fire and forget". Temporal offers "Event Sourcing" for your code. If your API sends an email but the DB fails to update, Temporal retries just the DB step. It creates resilient distributed systems.
4.  **SQLModel**: It solves the "Double declaration" problem (defining Pydantic schemas and
