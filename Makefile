.PHONY: install dev worker test lint format migrate migrate-tenant docker-up docker-down clean

# Install dependencies
install:
	uv sync

# Run API in dev mode
dev:
	uv run fastapi dev src/app/main.py

# Run Temporal worker
worker:
	uv run python -m src.app.temporal.worker

# Run tests
test:
	uv run pytest  -n auto --dist=loadscope

# Run tests with coverage
test-cov:
	uv run pytest --cov=src/app --cov-report=html

# Lint code
lint:
	uv run ruff check src/ tests/

# Format code
format:
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

# Run public schema migrations
migrate:
	uv run alembic upgrade head

# Run tenant schema migrations (usage: make migrate-tenant TENANT=acme)
migrate-tenant:
	uv run alembic upgrade head --tag=tenant_$(TENANT)

# Generate new migration
migration:
	uv run alembic revision --autogenerate -m "$(MSG)"

# Start all Docker services
docker-up:
	docker compose up -d

# Stop all Docker services
docker-down:
	docker compose down

# Build Docker images
docker-build:
	docker compose build

# View logs
logs:
	docker compose logs -f

# Clean up
clean:
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
