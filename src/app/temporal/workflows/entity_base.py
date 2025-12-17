"""
Base template for long-running entity workflows.

Entity workflows are "always-on" workflows tied to a business entity's lifecycle.
They receive commands via Updates and expose state via Queries.

Key features:
- Uses Updates instead of Signals (lower history footprint)
- Automatic Continue-As-New before history limits
- Queries for state inspection without history events

Example usage:
    @workflow.defn
    class OrderWorkflow(EntityWorkflowBase[OrderCtx, OrderCommand]):
        def __init__(self) -> None:
            super().__init__()
            self._items: list[str] = []
            self._status = "pending"

        async def _apply(self, ctx: OrderCtx, cmd: OrderCommand) -> None:
            if cmd.kind == "add_item":
                self._items.append(cmd.payload["item_id"])
            elif cmd.kind == "complete":
                self._status = "completed"

        def _get_state(self) -> dict:
            return {"items": self._items, "status": self._status}
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    pass

from temporalio import workflow

# Type variables for entity context and commands
TCtx = TypeVar("TCtx")
TCmd = TypeVar("TCmd")


@dataclass(frozen=True)
class EntityCtx:
    """Base context for entity workflows."""

    tenant_id: str
    entity_id: str
    entity_type: str


@dataclass(frozen=True)
class Command:
    """Base command for entity workflows."""

    kind: str
    payload: dict[str, object] = field(default_factory=dict)


# History guardrail settings
HISTORY_WARNING_THRESHOLD = 8000  # Continue-As-New before 10k warning
IDLE_TIMEOUT = timedelta(minutes=5)


@workflow.defn
class EntityWorkflowBase(Generic[TCtx, TCmd]):
    """
    Base class for long-running entity workflows.

    Subclasses must implement:
    - _apply(ctx, cmd): Process a command
    - _get_state(): Return current state for queries

    This base class provides:
    - Automatic Continue-As-New when history grows too large
    - Update handlers for low-history command submission
    - Query handlers for zero-history state inspection
    - Graceful shutdown mechanism

    Example usage:
        @workflow.defn
        class OrderWorkflow(EntityWorkflowBase[OrderCtx, OrderCommand]):
            def __init__(self) -> None:
                super().__init__()
                self._items: list[str] = []
                self._status = "pending"

            async def _apply(self, ctx: OrderCtx, cmd: OrderCommand) -> None:
                if cmd.kind == "add_item":
                    await workflow.execute_activity(add_item_activity, ...)
                    self._items.append(cmd.payload["item_id"])

            def _get_state(self) -> dict:
                return {"items": self._items, "status": self._status}
    """

    def __init__(self) -> None:
        self._pending: list[Any] = []
        self._done: bool = False

    @workflow.run
    async def run(self, ctx: TCtx) -> None:
        """
        Main workflow loop with Continue-As-New guardrails.

        This loop:
        1. Waits for commands or timeout
        2. Processes pending commands
        3. Checks history length and continues-as-new if needed
        """
        while not self._done:
            # Wait for commands or timeout
            await workflow.wait_condition(
                lambda: bool(self._pending) or self._done,
                timeout=IDLE_TIMEOUT,
            )

            # Process pending commands
            while self._pending:
                cmd = self._pending.pop(0)
                await self._apply(ctx, cmd)

            # History bloat prevention
            info = workflow.info()
            history_length = info.get_current_history_length()
            if info.is_continue_as_new_suggested() or history_length > HISTORY_WARNING_THRESHOLD:
                workflow.logger.info(
                    f"Continuing as new to cap history (current: {history_length})"
                )
                workflow.continue_as_new(ctx)

    @workflow.update
    async def submit(self, cmd: TCmd) -> None:
        """
        Submit a command to the workflow (low history footprint).

        Updates create minimal history events compared to Signals.
        The command is queued and processed in the main workflow loop.
        """
        self._pending.append(cmd)

    @workflow.update
    async def complete(self) -> None:
        """Mark the entity workflow as complete (graceful shutdown)."""
        self._done = True

    @workflow.query
    def status(self) -> dict[str, object]:
        """
        Query current workflow status (no history events).

        Queries are zero-cost operations that don't add to history.
        Perfect for monitoring and inspection.
        """
        return {
            "pending_commands": len(self._pending),
            "done": self._done,
            "state": self._get_state(),
        }

    @abstractmethod
    async def _apply(self, ctx: TCtx, cmd: TCmd) -> None:
        """
        Process a command. Implement in subclass.

        Args:
            ctx: Entity context with tenant_id, entity_id, etc.
            cmd: Command to process

        This is where you execute activities and update internal state.
        """
        pass

    @abstractmethod
    def _get_state(self) -> dict[str, object]:
        """
        Return current state for queries. Implement in subclass.

        Returns:
            dict: Current state snapshot

        This should be lightweight and fast - it's called on every status query.
        """
        pass
