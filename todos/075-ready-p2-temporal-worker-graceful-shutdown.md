---
status: ready
priority: p2
issue_id: "075"
tags: [architecture, temporal, shutdown, reliability]
dependencies: []
---

# Temporal Worker Missing Graceful Shutdown

## Problem Statement
The worker cleanup only disposes sync engine. It doesn't stop workers gracefully, wait for in-flight activities to complete, or close the Temporal client connection.

## Findings
- Location: `src/app/temporal/worker.py:233-252`
- Only `dispose_sync_engine()` called in finally block
- No worker shutdown signal
- No wait for in-flight activities
- Temporal client connection not closed
- Abrupt termination causes activity failures

## Proposed Solutions

### Option 1: Implement proper graceful shutdown
- **Pros**: Clean termination, no lost work, proper resource cleanup
- **Cons**: More complex shutdown logic
- **Effort**: Medium
- **Risk**: Low

```python
import signal
import asyncio

class WorkerManager:
    def __init__(self):
        self.workers: list[Worker] = []
        self.shutdown_event = asyncio.Event()

    async def run(self):
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._signal_shutdown)

        try:
            # Start workers
            await asyncio.gather(*[w.run() for w in self.workers])
        finally:
            await self._graceful_shutdown()

    def _signal_shutdown(self):
        logger.info("Shutdown signal received")
        self.shutdown_event.set()

    async def _graceful_shutdown(self, timeout: float = 30.0):
        logger.info("Starting graceful shutdown...")

        # Stop accepting new work
        for worker in self.workers:
            await worker.shutdown()

        # Wait for in-flight activities (with timeout)
        logger.info(f"Waiting up to {timeout}s for in-flight activities...")

        # Close Temporal client
        await client.close()

        # Dispose database engines
        dispose_sync_engine()
        logger.info("Graceful shutdown complete")
```

## Recommended Action
Implement WorkerManager with proper signal handling and graceful shutdown sequence.

## Technical Details
- **Affected Files**: `src/app/temporal/worker.py`
- **Related Components**: Temporal activities, database connections
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- Temporal Python SDK shutdown docs

## Acceptance Criteria
- [ ] Signal handlers for SIGTERM/SIGINT
- [ ] Workers stop accepting new work on shutdown
- [ ] Wait for in-flight activities with timeout
- [ ] Temporal client properly closed
- [ ] Database engines disposed last
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Graceful shutdown is critical for workflow reliability
- Order of cleanup matters: workers → client → resources

## Notes
Source: Triage session on 2025-12-18
