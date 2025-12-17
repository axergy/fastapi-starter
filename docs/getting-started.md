# Getting Started

Get up and running with the FastAPI Multi-Tenant SaaS Starter in minutes.

## Prerequisites

Before you begin, ensure you have the following installed:

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Docker | 24.0+ | Container runtime |
| Docker Compose | 2.20+ | Multi-container orchestration |
| Python | 3.11+ | Application runtime |
| uv | 0.4+ | Package manager (optional for local dev) |

### Installing uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/fastapi-starter.git
cd fastapi-starter
```

### 2. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

**Important:** Update these values in `.env`:

```bash
# REQUIRED: Change for security
JWT_SECRET_KEY=your-secret-key-at-least-32-characters-long

# Database connection
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/app

# Optional: Email service (Resend)
RESEND_API_KEY=re_xxxxx
```

### 3. Start Services

```bash
# Start all services (PostgreSQL, Redis, Temporal, API)
make docker-up

# Or with Docker Compose directly
docker compose up -d
```

This starts:

| Service | Port | Description |
|---------|------|-------------|
| API | 8000 | FastAPI application |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Rate limiting cache |
| Temporal | 7233 | Workflow orchestration |
| Temporal UI | 8080 | Workflow dashboard |

### 4. Verify Services

```bash
# Check all services are running
docker compose ps

# Check API health
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "version": "1.0.0"}
```

### 5. Open Swagger UI

Navigate to [http://localhost:8000/docs](http://localhost:8000/docs) to explore the API.

## First User Registration

### Register a User with New Tenant

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "SecureP@ssw0rd!2024",
    "full_name": "Admin User",
    "tenant_name": "Acme Corporation",
    "tenant_slug": "acme"
  }'
```

**Response (202 Accepted):**

```json
{
  "message": "Registration started. Tenant is being provisioned.",
  "tenant_slug": "acme",
  "workflow_id": "tenant-provision-acme"
}
```

> **Note:** The response is `202 Accepted` because tenant provisioning happens asynchronously via Temporal workflow.

### Check Provisioning Status

```bash
curl http://localhost:8000/api/v1/tenants/acme/status
```

**Response:**

```json
{
  "slug": "acme",
  "status": "ready",
  "name": "Acme Corporation"
}
```

Wait until `status` is `ready` before proceeding.

### Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: acme" \
  -d '{
    "email": "admin@example.com",
    "password": "SecureP@ssw0rd!2024"
  }'
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Access Protected Endpoints

```bash
# Get current user profile
curl http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Tenant-ID: acme"
```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/db` |
| `JWT_SECRET_KEY` | Secret for JWT signing (min 32 chars) | `your-very-secure-random-key-here` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug mode |
| `APP_ENV` | `production` | Environment (development/testing/production) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `GLOBAL_RATE_LIMIT_PER_SECOND` | `10` | API rate limit |
| `GLOBAL_RATE_LIMIT_BURST` | `20` | Rate limit burst capacity |
| `REDIS_URL` | `None` | Redis for distributed rate limiting |
| `TEMPORAL_HOST` | `localhost:7233` | Temporal server address |
| `RESEND_API_KEY` | `None` | Email service API key |

### Database Configuration

```bash
# Separate URL for migrations (optional, for elevated privileges)
DATABASE_MIGRATIONS_URL=postgresql+asyncpg://admin:adminpass@host:5432/db

# Statement cache (keep at 0 for multi-tenancy)
DATABASE_STATEMENT_CACHE_SIZE=0

# SSL mode for production
DATABASE_SSL_MODE=require
```

## Local Development (Without Docker)

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e ".[dev]"
```

### 2. Start External Services

You'll need PostgreSQL, Redis, and Temporal running:

```bash
# Start only infrastructure services
docker compose up -d db redis temporal temporal-db
```

### 3. Run Migrations

```bash
# Activate virtual environment
source .venv/bin/activate

# Run public schema migrations
alembic upgrade head
```

### 4. Start the API

```bash
# Using Makefile
make dev

# Or directly
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Start the Temporal Worker

In a separate terminal:

```bash
# Using Makefile
make worker

# Or directly
python -m src.app.temporal.worker
```

## Project Structure

```
fastapi-starter/
├── src/
│   ├── app/                 # Application code
│   │   ├── api/             # HTTP routes
│   │   ├── core/            # Configuration, DB, security
│   │   ├── models/          # SQLModel definitions
│   │   ├── schemas/         # Pydantic DTOs
│   │   ├── repositories/    # Data access layer
│   │   ├── services/        # Business logic
│   │   └── temporal/        # Background workflows
│   ├── alembic/             # Database migrations
│   └── main.py              # Entry point
├── tests/                   # Test suite
├── compose.yml              # Docker Compose config
├── Dockerfile               # API container
├── Makefile                 # Development commands
└── pyproject.toml           # Dependencies
```

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make install` | Install dependencies |
| `make dev` | Run API in development mode |
| `make worker` | Run Temporal worker |
| `make test` | Run all tests |
| `make test-cov` | Run tests with coverage |
| `make lint` | Run linter (ruff) |
| `make format` | Format code |
| `make migrate` | Run public migrations |
| `make migrate-tenant` | Run tenant migrations |
| `make docker-up` | Start Docker services |
| `make docker-down` | Stop Docker services |
| `make logs` | View Docker logs |

## Common Tasks

### Create a New Migration

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "Add new table"

# Create empty migration
alembic revision -m "Custom migration"
```

### Invite a User to Tenant

```bash
curl -X POST http://localhost:8000/api/v1/invites \
  -H "Authorization: Bearer <admin_token>" \
  -H "X-Tenant-ID: acme" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "role": "member"
  }'
```

### View Temporal Workflows

Open [http://localhost:8080](http://localhost:8080) to access the Temporal UI and monitor provisioning workflows.

## Troubleshooting

### "Tenant is still provisioning"

The tenant schema is being created. Check Temporal UI for workflow status:

```bash
# Check workflow status via API
curl http://localhost:8000/api/v1/tenants/acme/status
```

### "Connection refused" to database

Ensure PostgreSQL is running:

```bash
docker compose ps db
docker compose logs db
```

### "JWT_SECRET_KEY validation error"

The secret key must be at least 32 characters:

```bash
# Generate a secure key
openssl rand -base64 32
```

### Rate limiting in development

Disable rate limiting for testing:

```bash
APP_ENV=testing uvicorn src.main:app --reload
```

## Next Steps

- [Architecture Overview](architecture/overview.md) - Understand the system design
- [Multi-Tenancy Guide](architecture/multi-tenancy.md) - Learn about tenant isolation
- [Security Guide](security.md) - Review security features
- [API Documentation](http://localhost:8000/docs) - Explore all endpoints
