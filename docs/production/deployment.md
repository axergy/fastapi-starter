# Production Deployment

This guide covers deploying the FastAPI Multi-Tenant SaaS Starter to production environments.

## Deployment Options

### Docker Compose (Simple)

Suitable for single-server deployments:

```yaml
# compose.prod.yml
services:
  api:
    image: your-registry/fastapi-starter:latest
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - REDIS_URL=${REDIS_URL}
      - APP_ENV=production
    ports:
      - "8000:8000"
    deploy:
      replicas: 2
      restart_policy:
        condition: on-failure

  worker:
    image: your-registry/fastapi-starter-worker:latest
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - TEMPORAL_HOST=${TEMPORAL_HOST}
    deploy:
      replicas: 1
```

### Kubernetes (Scalable)

For larger deployments with auto-scaling:

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fastapi-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fastapi-api
  template:
    metadata:
      labels:
        app: fastapi-api
    spec:
      containers:
        - name: api
          image: your-registry/fastapi-starter:latest
          ports:
            - containerPort: 8000
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: database-url
            - name: JWT_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: jwt-secret
          resources:
            requests:
              cpu: "100m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 20
```

## Environment Configuration

### Required Production Settings

```bash
# Security (CRITICAL)
JWT_SECRET_KEY=<random-64-character-string>
DATABASE_SSL_MODE=require

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?ssl=require

# Redis (required for distributed rate limiting)
REDIS_URL=redis://host:6379/0

# Temporal
TEMPORAL_HOST=temporal.your-domain.com:7233

# Environment
APP_ENV=production
DEBUG=false
```

### Generate Secure JWT Key

```bash
# Using OpenSSL
openssl rand -base64 64

# Using Python
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Database Considerations

### Connection Pooling

Configure connection pooling based on your workload:

```python
# Recommended settings for production
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,           # Base connections
    max_overflow=20,        # Additional connections under load
    pool_timeout=30,        # Wait time for connection
    pool_recycle=1800,      # Recycle connections every 30 min
    pool_pre_ping=True,     # Check connection health
    connect_args={
        "statement_cache_size": 0,  # REQUIRED for multi-tenancy
        "ssl": "require",
    },
)
```

### Schema Tenancy and Pooling

With schema-per-tenant, each request may use a different `search_path`. Important considerations:

1. **Statement cache must be disabled** (`statement_cache_size=0`)
2. **Always reset search_path** after tenant operations
3. **Consider separate pools** for heavy tenants (optional)

```python
# Connection reset after tenant operations
async with get_tenant_session(schema_name) as session:
    # ... tenant operations ...
    pass
# search_path automatically reset to 'public'
```

### PostgreSQL Configuration

Recommended PostgreSQL settings for multi-tenant workloads:

```ini
# postgresql.conf
max_connections = 200
shared_buffers = 4GB
effective_cache_size = 12GB
work_mem = 64MB
maintenance_work_mem = 1GB
max_wal_size = 4GB

# For many schemas
max_locks_per_transaction = 256
```

## Temporal Deployment

### Temporal Server

Run Temporal with proper persistence:

```yaml
# temporal-deployment.yaml
services:
  temporal:
    image: temporalio/auto-setup:latest
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=${TEMPORAL_DB_PASSWORD}
      - POSTGRES_SEEDS=postgres-host
    ports:
      - "7233:7233"

  temporal-ui:
    image: temporalio/ui:latest
    environment:
      - TEMPORAL_ADDRESS=temporal:7233
    ports:
      - "8080:8080"
```

### Worker Deployment

Deploy workers separately for scaling:

```yaml
# worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: temporal-worker
spec:
  replicas: 2  # Scale based on workflow volume
  template:
    spec:
      containers:
        - name: worker
          image: your-registry/fastapi-starter-worker:latest
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: database-url
            - name: TEMPORAL_HOST
              value: temporal:7233
```

### Workflow Considerations

- **Idempotency**: All activities are designed for safe retries
- **Timeouts**: Configure appropriate timeouts for activities
- **Retry Policy**: Default retries handle transient failures

## Monitoring

### Health Checks

The API exposes health endpoints:

```bash
# Basic health check
GET /health
{"status": "healthy", "version": "1.0.0"}

# Detailed health (with database check)
GET /health/ready
{"status": "ready", "database": "connected", "redis": "connected"}
```

### Metrics to Monitor

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `tenant_provisioning_duration` | Time to provision tenant | > 5 minutes |
| `tenant_provisioning_failures` | Failed provisioning count | > 0 |
| `api_request_duration_p99` | 99th percentile latency | > 2 seconds |
| `rate_limit_rejections` | Rate-limited requests | Spike detection |
| `database_connection_pool_usage` | Pool utilization | > 80% |
| `audit_log_failures` | Failed audit writes | > 0 |

### Prometheus Metrics Example

```python
# Add to main.py for metrics export
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

### Logging

Structured logging with correlation IDs:

```python
# Logs include request context
{
    "timestamp": "2024-01-15T10:30:00Z",
    "level": "INFO",
    "message": "User logged in",
    "request_id": "abc-123-def",
    "tenant_id": "acme",
    "user_id": "user-456",
    "ip_address": "192.168.1.100"
}
```

### Failed Tenant Monitoring

Query for failed tenants:

```sql
-- Check failed tenants
SELECT id, slug, name, created_at
FROM public.tenants
WHERE status = 'failed'
ORDER BY created_at DESC;

-- Check provisioning workflow status
SELECT tenant_id, status, error_message, updated_at
FROM public.workflow_executions
WHERE workflow_type = 'TenantProvisioningWorkflow'
  AND status = 'failed';
```

## Scaling Strategies

### Horizontal API Scaling

The API is stateless and can scale horizontally:

```yaml
# Kubernetes HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fastapi-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### Database Scaling

Options for database scaling:

1. **Read Replicas** - For read-heavy workloads
2. **Connection Pooler** (PgBouncer) - For many connections
3. **Vertical Scaling** - Larger instance for more tenants
4. **Sharding** - Multiple database clusters for thousands of tenants

### Redis Scaling

For high-volume rate limiting:

```yaml
# Redis Cluster or AWS ElastiCache
REDIS_URL=redis://redis-cluster.example.com:6379/0
```

## Graceful Shutdown

The application supports graceful shutdown:

```python
# src/app/core/shutdown.py
async def wait_for_drain(timeout: int = 30) -> None:
    """Wait for in-flight requests to complete."""
    start = time.time()
    while request_tracker.active_requests > 0:
        if time.time() - start > timeout:
            logger.warning(f"Shutdown timeout, {request_tracker.active_requests} requests remaining")
            break
        await asyncio.sleep(0.1)
```

### Kubernetes Configuration

```yaml
spec:
  containers:
    - name: api
      lifecycle:
        preStop:
          exec:
            command: ["sleep", "5"]  # Allow load balancer to drain
      terminationGracePeriodSeconds: 60
```

## Migration Deployment

### Blue-Green Deployment

1. Deploy new version (green)
2. Run migrations on green database
3. Switch traffic to green
4. Keep blue as rollback option

### Rolling Deployment with Migrations

```bash
#!/bin/bash
# deploy.sh

# 1. Run public schema migrations
kubectl exec -it migration-pod -- alembic upgrade head

# 2. Run tenant migrations in parallel
kubectl exec -it migration-pod -- ./migrate-all-tenants.sh

# 3. Rolling update API pods
kubectl rollout restart deployment/fastapi-api

# 4. Verify health
kubectl rollout status deployment/fastapi-api
```

### Tenant Migration Script

```bash
#!/bin/bash
# migrate-all-tenants.sh

TENANT_SLUGS=$(psql -t -c "SELECT slug FROM tenants WHERE status = 'ready'")

for slug in $TENANT_SLUGS; do
    echo "Migrating tenant: $slug"
    alembic upgrade head --tag="tenant_$slug" &
done

wait  # Wait for all migrations to complete
echo "All tenant migrations complete"
```

## Security Checklist

Before going to production:

- [ ] Change `JWT_SECRET_KEY` from default
- [ ] Enable database SSL (`DATABASE_SSL_MODE=require`)
- [ ] Configure HTTPS/TLS termination at load balancer
- [ ] Set up Redis for distributed rate limiting
- [ ] Enable audit logging
- [ ] Configure proper CORS origins
- [ ] Set up log aggregation
- [ ] Configure backup strategy
- [ ] Set up monitoring and alerting
- [ ] Review and test disaster recovery

## Backup Strategy

### Database Backups

```bash
# Full database backup
pg_dump -Fc -h host -U user dbname > backup.dump

# Per-tenant backup (schema only)
pg_dump -Fc -n tenant_acme -h host -U user dbname > tenant_acme.dump
```

### Automated Backups

Use managed PostgreSQL services (AWS RDS, GCP Cloud SQL) for:
- Automated daily backups
- Point-in-time recovery
- Cross-region replication

## Disaster Recovery

### Recovery Procedures

1. **Database Recovery**
   ```bash
   pg_restore -h host -U user -d dbname backup.dump
   ```

2. **Tenant Schema Recovery**
   ```bash
   pg_restore -h host -U user -d dbname -n tenant_acme tenant_acme.dump
   ```

3. **Re-run Failed Migrations**
   ```bash
   alembic upgrade head --tag=tenant_acme
   ```

### RTO/RPO Considerations

| Scenario | RTO Target | RPO Target |
|----------|------------|------------|
| Database failure | 1 hour | 1 hour |
| Single tenant corruption | 15 minutes | 1 hour |
| Complete region failure | 4 hours | 1 hour |

## Next Steps

- [Security Guide](../security.md) - Production security hardening
- [Testing Guide](../development/testing.md) - CI/CD testing
- [Architecture Overview](../architecture/overview.md) - System design
