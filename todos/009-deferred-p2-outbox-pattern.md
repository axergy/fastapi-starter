---
status: deferred
priority: p2
issue_id: "009"
tags: [temporal, reliability, outbox-pattern]
dependencies: []
---

# Workflow Start Reliability (Outbox Pattern)

## Problem Statement
Registration commits DB transaction, then starts Temporal workflow. If Temporal is unavailable after DB commit, the tenant gets stuck in "provisioning" state and the user cannot retry due to uniqueness constraints.

## Findings
- Location: `src/app/services/registration_service.py`
  - DB transaction committed before workflow starts
  - If `client.start_workflow()` fails, tenant already exists in DB
- **Failure scenario:**
  1. User registers → DB commit succeeds → tenant created
  2. Temporal unavailable → workflow fails to start
  3. User sees error but tenant exists
  4. User cannot re-register (email/slug unique constraint)
  5. Tenant stuck in "provisioning" forever

## Proposed Solutions

### Option 1: Outbox Pattern (Full Solution)
- **Pros**: Guaranteed workflow start, standard pattern for event-driven systems
- **Cons**: Requires new table, background worker, more complexity
- **Effort**: Large (3-5 days)
- **Risk**: Low (well-established pattern)

#### Implementation Requirements

**1. Database Migration**
Create new `outbox_events` table:

```python
# src/alembic/versions/XXX_add_outbox_table.py
def upgrade() -> None:
    op.create_table(
        'outbox_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('aggregate_id', sa.UUID(), nullable=False),  # tenant_id, user_id, etc.
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=3),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('processed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_outbox_events_status_created_at', 'status', 'created_at'),
        sa.Index('ix_outbox_events_aggregate_id', 'aggregate_id'),
    )
```

**2. Outbox Model**
```python
# src/app/models/public/outbox.py
class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(100))
    aggregate_id: Mapped[UUID]
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    retry_count: Mapped[int] = mapped_column(default=0)
    max_retries: Mapped[int] = mapped_column(default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
```

**3. Update Registration Service**
```python
# src/app/services/registration_service.py
async def register(self, data: RegistrationRequest) -> RegistrationResponse:
    async with self.session.begin():
        # Create tenant
        tenant = await self.tenant_repo.create(...)
        user = await self.user_repo.create(...)

        # Instead of starting workflow directly, write to outbox
        outbox_event = OutboxEvent(
            event_type="tenant_provisioning",
            aggregate_id=tenant.id,
            payload={
                "tenant_id": str(tenant.id),
                "user_id": str(user.id),
                "workflow_id": f"provision-tenant-{tenant.id}",
            },
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(outbox_event)
        # Transaction commits atomically with both tenant and outbox event

    return RegistrationResponse(...)
```

**4. Outbox Processor (Background Worker)**
Two approaches:

**Approach A: Dedicated Python Worker**
```python
# src/app/workers/outbox_processor.py
class OutboxProcessor:
    def __init__(self, session_factory, temporal_client):
        self.session_factory = session_factory
        self.temporal_client = temporal_client
        self.running = False

    async def start(self):
        self.running = True
        while self.running:
            try:
                await self._process_batch()
                await asyncio.sleep(5)  # Poll every 5 seconds
            except Exception as e:
                logger.error(f"Outbox processing error: {e}")
                await asyncio.sleep(10)

    async def _process_batch(self):
        async with self.session_factory() as session:
            # Fetch pending events
            query = (
                select(OutboxEvent)
                .where(OutboxEvent.status == "pending")
                .where(OutboxEvent.retry_count < OutboxEvent.max_retries)
                .order_by(OutboxEvent.created_at)
                .limit(10)
                .with_for_update(skip_locked=True)  # Prevent concurrent processing
            )
            result = await session.execute(query)
            events = result.scalars().all()

            for event in events:
                try:
                    await self._process_event(event)
                    event.status = "processed"
                    event.processed_at = datetime.now(timezone.utc)
                except Exception as e:
                    event.retry_count += 1
                    event.last_error = str(e)
                    if event.retry_count >= event.max_retries:
                        event.status = "failed"
                    logger.error(f"Failed to process event {event.id}: {e}")

                await session.commit()

    async def _process_event(self, event: OutboxEvent):
        if event.event_type == "tenant_provisioning":
            payload = event.payload
            await self.temporal_client.start_workflow(
                TenantProvisioningWorkflow.run,
                id=payload["workflow_id"],
                task_queue="tenant-provisioning",
                args=[payload["tenant_id"], payload["user_id"]],
            )
        # Add other event types here

# In main application startup:
# async def start_outbox_processor():
#     processor = OutboxProcessor(async_session_factory, temporal_client)
#     asyncio.create_task(processor.start())
```

**Approach B: Temporal Workflow for Processing**
```python
# src/app/workflows/outbox_processor_workflow.py
@workflow.defn
class OutboxProcessorWorkflow:
    @workflow.run
    async def run(self):
        while True:
            await workflow.execute_activity(
                process_outbox_batch,
                schedule_to_close_timeout=timedelta(minutes=5),
            )
            await asyncio.sleep(5)

@activity.defn
async def process_outbox_batch():
    # Similar to _process_batch above
    pass
```

**5. Monitoring & Observability**
- Add metrics for outbox queue depth
- Alert on events stuck in "pending" status > 5 minutes
- Alert on high retry counts
- Dashboard showing event processing lag

**6. Testing**
```python
# tests/unit/test_outbox_processor.py
async def test_outbox_processes_pending_events():
    # Create pending outbox event
    # Run processor
    # Verify workflow started and event marked processed

async def test_outbox_retries_on_temporal_failure():
    # Mock Temporal failure
    # Verify retry_count increments
    # Verify event not marked failed until max retries

async def test_outbox_concurrent_processing():
    # Multiple processors should handle different events
    # Test skip_locked behavior
```

### Option 2: Sweeper Job for Stuck Tenants (Simple Alternative)
- **Pros**: Simpler, no new infrastructure, handles edge cases
- **Cons**: Delayed recovery (only runs periodically), doesn't prevent the issue
- **Effort**: Small (4-8 hours)
- **Risk**: Low

#### Implementation Requirements

**1. Temporal Scheduled Workflow**
```python
# src/app/workflows/tenant_sweeper_workflow.py
@workflow.defn
class TenantSweeperWorkflow:
    @workflow.run
    async def run(self):
        """Runs every 15 minutes to find and fix stuck tenants."""
        stuck_tenants = await workflow.execute_activity(
            find_stuck_tenants,
            schedule_to_close_timeout=timedelta(minutes=5),
        )

        for tenant_id in stuck_tenants:
            # Start provisioning workflow for stuck tenant
            await workflow.execute_child_workflow(
                TenantProvisioningWorkflow.run,
                id=f"provision-tenant-{tenant_id}-retry-{int(time.time())}",
                args=[tenant_id],
            )

@activity.defn
async def find_stuck_tenants() -> list[str]:
    """Find tenants in 'provisioning' status for more than 5 minutes."""
    async with async_session_factory() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        query = (
            select(Tenant.id)
            .where(Tenant.status == TenantStatus.PROVISIONING)
            .where(Tenant.created_at < cutoff)
        )
        result = await session.execute(query)
        return [str(tenant_id) for tenant_id in result.scalars().all()]

# Schedule the workflow:
# await client.start_workflow(
#     TenantSweeperWorkflow.run,
#     id="tenant-sweeper",
#     task_queue="system-tasks",
#     cron_schedule="*/15 * * * *",  # Every 15 minutes
# )
```

**2. Update Provisioning Workflow to be Idempotent**
```python
# src/app/workflows/tenant_provisioning.py
@workflow.defn
class TenantProvisioningWorkflow:
    @workflow.run
    async def run(self, tenant_id: str, user_id: str | None = None):
        # Check current tenant status first
        tenant_status = await workflow.execute_activity(
            get_tenant_status,
            tenant_id,
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # Skip if already provisioned
        if tenant_status == TenantStatus.ACTIVE:
            workflow.logger.info(f"Tenant {tenant_id} already provisioned")
            return

        # Continue with provisioning steps...
        # Each activity should be idempotent
```

**3. Monitoring**
- Alert on number of stuck tenants > 0
- Track sweeper execution frequency
- Log when tenants are recovered

**4. Testing**
```python
# tests/unit/test_tenant_sweeper.py
async def test_sweeper_finds_stuck_tenants():
    # Create tenant in provisioning status from 10 minutes ago
    # Run find_stuck_tenants activity
    # Verify tenant found

async def test_sweeper_ignores_recent_tenants():
    # Create tenant in provisioning status from 1 minute ago
    # Run find_stuck_tenants activity
    # Verify tenant not found

async def test_provisioning_workflow_idempotent():
    # Run workflow on already-provisioned tenant
    # Verify no duplicate work done
```

### Option 3: Idempotent Workflow Start with Retry
- **Pros**: No new infrastructure, immediate retry
- **Cons**: Still has a window of failure, more complex error handling
- **Effort**: Medium (1-2 days)
- **Risk**: Medium

Not recommended - adds complexity without guarantees.

## Recommended Action

**Status: DEFERRED**

This is a future enhancement. The risk window is small (Temporal is generally reliable), and the impact is low (only affects users during Temporal outages).

**Recommendation:**
1. **Short-term (Implement First)**: Option 2 (Sweeper Job)
   - Simple, low-risk mitigation
   - Provides recovery mechanism for any stuck tenants
   - Implementation time: 4-8 hours
   - Should be implemented if this becomes a real problem in production

2. **Long-term (If Needed)**: Option 1 (Outbox Pattern)
   - Only implement if:
     - Temporal downtime becomes frequent
     - Business requires guaranteed workflow starts
     - System needs full event-sourcing capabilities
   - Implementation time: 3-5 days
   - Requires ongoing maintenance and monitoring

**Current Priority**: P2 (Nice-to-have enhancement)
- No known instances of this issue in production
- Temporal has high availability
- Sweeper can recover if issue occurs

## Technical Details
- **Affected Files**:
  - `src/app/services/registration_service.py` (modify registration flow)
  - New: `src/alembic/versions/XXX_add_outbox_table.py` (outbox only)
  - New: `src/app/models/public/outbox.py` (outbox only)
  - New: `src/app/workers/outbox_processor.py` (outbox only)
  - New: `src/app/workflows/tenant_sweeper_workflow.py` (sweeper only)
- **Related Components**: Registration, tenant provisioning, Temporal
- **Database Changes**: Yes (new outbox table if using Option 1)
- **Infrastructure Changes**: Background worker process or scheduled Temporal workflow

## Resources
- Original finding: REVIEW.md - Nice-to-Have
- Related issues: None
- References:
  - [Transactional Outbox Pattern](https://microservices.io/patterns/data/transactional-outbox.html)
  - [Temporal Best Practices](https://docs.temporal.io/dev-guide/python/best-practices)

## Acceptance Criteria

### If Implementing Sweeper (Recommended First Step)
- [ ] Sweeper workflow created and scheduled (every 15 minutes)
- [ ] Finds tenants in "provisioning" status > 5 minutes old
- [ ] Starts provisioning workflow for stuck tenants
- [ ] Provisioning workflow is idempotent (safe to retry)
- [ ] Tests cover stuck tenant detection and recovery
- [ ] Monitoring alerts on stuck tenant count

### If Implementing Outbox (Future Enhancement)
- [ ] Outbox table migration created
- [ ] OutboxEvent model created
- [ ] Registration service writes to outbox instead of starting workflow directly
- [ ] Outbox processor implemented (Python worker or Temporal workflow)
- [ ] Processor handles retries and marks events as processed/failed
- [ ] Monitoring dashboard for outbox queue depth and lag
- [ ] Tests cover outbox write, processing, retries, and failure scenarios
- [ ] Documentation updated with outbox pattern usage

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P2 (Reliability Enhancement)
- Estimated effort: Large (outbox) / Small (sweeper)

**Learnings:**
- Outbox pattern is the gold standard for distributed transactions
- A simpler sweeper can mitigate the issue without full outbox implementation
- Consider Temporal workflow for outbox processing to avoid new infrastructure

### 2025-12-16 - Detailed Documentation
**By:** Claude Code
**Actions:**
- Marked status as "deferred" (P2 enhancement, not urgent)
- Documented full implementation requirements for outbox pattern
- Documented simpler sweeper alternative with code examples
- Added testing, monitoring, and acceptance criteria
- Recommended implementing sweeper first if issue becomes real

**Learnings:**
- Outbox pattern requires significant infrastructure (5+ new files)
- Sweeper is 90% simpler and handles 95% of cases
- Should only implement outbox if Temporal reliability becomes a real issue
- Both solutions require idempotent workflow design

## Notes
Source: REVIEW.md analysis on 2025-12-16

This is a P2 enhancement, not a critical bug. The risk window is small and impact is low. Only implement if:
1. Temporal downtime becomes a recurring problem
2. Business requires guaranteed workflow starts
3. Stuck tenants are reported by users

Start with the sweeper if implementing anything - it's 90% simpler and handles the vast majority of edge cases.
