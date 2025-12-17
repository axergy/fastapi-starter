# Kubernetes Deployment Manifests

This directory contains Kubernetes deployment manifests for the Temporal worker infrastructure.

## Worker Types

### Tenant Workers (`worker-tenant.yaml`)

Handles tenant-scoped workflows with lower concurrency settings optimized for heavy database operations:
- Tenant provisioning
- Tenant deletion
- User onboarding

**Default Configuration:**
- 2 replicas (scales 2-10 with HPA)
- 512Mi-1Gi memory
- 500m-1000m CPU
- Max concurrent activities: 20
- Max concurrent workflow tasks: 20

**Deploy:**
```bash
kubectl apply -f worker-tenant.yaml
```

### Jobs Workers (`worker-jobs.yaml`)

Handles system-level background jobs with higher concurrency for lightweight operations:
- Token cleanup
- Scheduled maintenance tasks
- System-wide cron jobs

**Default Configuration:**
- 1 replica (scales 1-3 with HPA)
- 256Mi-512Mi memory
- 250m-500m CPU
- Max concurrent activities: 50
- Max concurrent workflow tasks: 50

**Deploy:**
```bash
kubectl apply -f worker-jobs.yaml
```

## Usage

### Deploy All Workers
```bash
kubectl apply -f deploy/k8s/
```

### Scale Workers Manually
```bash
# Scale tenant workers
kubectl scale deployment temporal-worker-tenant --replicas=5

# Scale jobs workers
kubectl scale deployment temporal-worker-jobs --replicas=2
```

### Check Worker Health
```bash
# Port forward to health endpoint
kubectl port-forward svc/temporal-worker-tenant 8001:8001

# Check health
curl http://localhost:8001/health
curl http://localhost:8001/ready
```

### View Logs
```bash
# Tenant workers
kubectl logs -l workload=tenant --tail=100 -f

# Jobs workers
kubectl logs -l workload=jobs --tail=100 -f
```

## Configuration

### Required Secrets

Create a secret named `app-secrets` with:
- `database-url`: PostgreSQL connection string
- `stripe-secret-key`: Stripe API key (for tenant provisioning)
- `smtp-username`: SMTP username (for email sending)
- `smtp-password`: SMTP password

```bash
kubectl create secret generic app-secrets \
  --from-literal=database-url="postgresql://..." \
  --from-literal=stripe-secret-key="sk_..." \
  --from-literal=smtp-username="..." \
  --from-literal=smtp-password="..."
```

### Required ConfigMaps

Create a configmap named `app-config` with:
- `smtp-host`: SMTP server hostname
- `smtp-port`: SMTP server port

```bash
kubectl create configmap app-config \
  --from-literal=smtp-host="smtp.example.com" \
  --from-literal=smtp-port="587"
```

### Environment Variables

Key environment variables (set in deployment manifests):
- `TEMPORAL_HOST`: Temporal server address (default: `temporal:7233`)
- `TEMPORAL_NAMESPACE`: Temporal namespace (default: `default`)
- `TEMPORAL_QUEUE_PREFIX`: Queue name prefix (default: `saas`)
- `TEMPORAL_QUEUE_SHARDS`: Number of tenant queue shards (default: `1`, scale to 32/64)
- `APP_ENV`: Application environment (`production`, `staging`, etc.)

## Horizontal Pod Autoscaling

Both deployments include HPA configurations that scale based on:
- CPU utilization (target: 70%)
- Memory utilization (target: 80%)

The HPA will automatically adjust replicas within the defined min/max bounds.

## Health Checks

Each worker includes both liveness and readiness probes:

**Liveness Probe:**
- Path: `/health`
- Initial delay: 30s
- Period: 10s
- Failure threshold: 3

**Readiness Probe:**
- Path: `/ready`
- Initial delay: 10s
- Period: 5s
- Failure threshold: 2

## Monitoring

Monitor worker performance using these Temporal metrics:
- `temporal_schedule_to_start_latency`: Time from workflow scheduled to started
- `temporal_activity_execution_latency`: Activity execution time
- `temporal_workflow_task_queue_latency`: Task queue processing latency

Scale workers when schedule-to-start latency increases beyond acceptable thresholds.

## Development Mode

For local development, run all workers in a single process:

```bash
python -m src.app.temporal.worker --workload all
```

This is the default behavior and maintains backward compatibility with existing deployments.
