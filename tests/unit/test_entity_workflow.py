"""Tests for entity workflow base template."""

from dataclasses import dataclass
from typing import Any

import pytest
from temporalio import workflow
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from src.app.temporal.workflows.entity_base import (
    HISTORY_WARNING_THRESHOLD,
    Command,
    EntityCtx,
    EntityWorkflowBase,
)

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class TestCtx(EntityCtx):
    """Test context extending EntityCtx."""

    extra_field: str = "test"


@dataclass(frozen=True)
class TestCommand(Command):
    """Test command extending Command."""

    pass


@workflow.defn
class TestEntityWorkflow(EntityWorkflowBase[TestCtx, TestCommand]):
    """Concrete test implementation of EntityWorkflowBase."""

    def __init__(self) -> None:
        super().__init__()
        self._processed_commands: list[str] = []
        self._counter = 0

    async def _apply(self, ctx: TestCtx, cmd: TestCommand) -> None:
        """Process test commands."""
        self._processed_commands.append(cmd.kind)
        if cmd.kind == "increment":
            self._counter += 1
        elif cmd.kind == "add":
            self._counter += cmd.payload.get("value", 0)
        elif cmd.kind == "shutdown":
            self._done = True

    def _get_state(self) -> dict[str, Any]:
        """Return test state."""
        return {
            "processed_commands": self._processed_commands,
            "counter": self._counter,
        }


class TestEntityWorkflowBase:
    """Tests for EntityWorkflowBase template."""

    @pytest.mark.asyncio
    async def test_entity_workflow_initialization(self) -> None:
        """Entity workflow should initialize with empty state."""
        async with await WorkflowEnvironment.start_time_skipping() as env:  # noqa: SIM117
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[TestEntityWorkflow],
            ):
                # Start workflow
                handle = await env.client.start_workflow(
                    TestEntityWorkflow.run,
                    TestCtx(
                        tenant_id="tenant-123",
                        entity_id="entity-456",
                        entity_type="test",
                    ),
                    id="test-entity-workflow",
                    task_queue="test-queue",
                )

                # Query initial state
                status = await handle.query(TestEntityWorkflow.status)
                assert status["pending_commands"] == 0
                assert status["done"] is False
                assert status["state"]["counter"] == 0
                assert status["state"]["processed_commands"] == []

                # Complete workflow
                await handle.execute_update(TestEntityWorkflow.complete)

    @pytest.mark.asyncio
    async def test_entity_workflow_submit_and_query(self) -> None:
        """Entity workflow should process commands via submit update."""
        async with await WorkflowEnvironment.start_time_skipping() as env:  # noqa: SIM117
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[TestEntityWorkflow],
            ):
                # Start workflow
                handle = await env.client.start_workflow(
                    TestEntityWorkflow.run,
                    TestCtx(
                        tenant_id="tenant-123",
                        entity_id="entity-456",
                        entity_type="test",
                    ),
                    id="test-entity-submit",
                    task_queue="test-queue",
                )

                # Submit commands
                await handle.execute_update(
                    TestEntityWorkflow.submit,
                    TestCommand(kind="increment"),
                )
                await handle.execute_update(
                    TestEntityWorkflow.submit,
                    TestCommand(kind="add", payload={"value": 5}),
                )

                # Allow workflow to process
                await env.sleep(0.1)

                # Query state
                status = await handle.query(TestEntityWorkflow.status)
                assert status["state"]["counter"] == 6  # 1 + 5
                assert len(status["state"]["processed_commands"]) == 2
                assert "increment" in status["state"]["processed_commands"]
                assert "add" in status["state"]["processed_commands"]

                # Complete workflow
                await handle.execute_update(TestEntityWorkflow.complete)

    @pytest.mark.asyncio
    async def test_entity_workflow_graceful_shutdown(self) -> None:
        """Entity workflow should shut down gracefully via complete update."""
        async with await WorkflowEnvironment.start_time_skipping() as env:  # noqa: SIM117
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[TestEntityWorkflow],
            ):
                # Start workflow
                handle = await env.client.start_workflow(
                    TestEntityWorkflow.run,
                    TestCtx(
                        tenant_id="tenant-123",
                        entity_id="entity-456",
                        entity_type="test",
                    ),
                    id="test-entity-shutdown",
                    task_queue="test-queue",
                )

                # Check not done
                status = await handle.query(TestEntityWorkflow.status)
                assert status["done"] is False

                # Complete workflow
                await handle.execute_update(TestEntityWorkflow.complete)

                # Allow workflow to finish
                await env.sleep(0.1)

                # Query final state
                status = await handle.query(TestEntityWorkflow.status)
                assert status["done"] is True

    @pytest.mark.asyncio
    async def test_entity_workflow_command_processing(self) -> None:
        """Entity workflow should process multiple commands in order."""
        async with await WorkflowEnvironment.start_time_skipping() as env:  # noqa: SIM117
            async with Worker(
                env.client,
                task_queue="test-queue",
                workflows=[TestEntityWorkflow],
            ):
                # Start workflow
                handle = await env.client.start_workflow(
                    TestEntityWorkflow.run,
                    TestCtx(
                        tenant_id="tenant-123",
                        entity_id="entity-456",
                        entity_type="test",
                    ),
                    id="test-entity-commands",
                    task_queue="test-queue",
                )

                # Submit multiple commands
                commands = [
                    TestCommand(kind="increment"),
                    TestCommand(kind="increment"),
                    TestCommand(kind="add", payload={"value": 10}),
                ]
                for cmd in commands:
                    await handle.execute_update(TestEntityWorkflow.submit, cmd)

                # Allow processing
                await env.sleep(0.1)

                # Verify state
                status = await handle.query(TestEntityWorkflow.status)
                assert status["state"]["counter"] == 12  # 1 + 1 + 10
                assert len(status["state"]["processed_commands"]) == 3

                # Complete workflow
                await handle.execute_update(TestEntityWorkflow.complete)


class TestEntityWorkflowConstants:
    """Tests for entity workflow constants."""

    def test_history_warning_threshold(self) -> None:
        """History warning threshold should be set to prevent bloat."""
        assert HISTORY_WARNING_THRESHOLD == 8000
        assert HISTORY_WARNING_THRESHOLD < 10000  # Below Temporal's default warning

    def test_entity_ctx_structure(self) -> None:
        """EntityCtx should have required fields."""
        ctx = EntityCtx(
            tenant_id="tenant-123",
            entity_id="entity-456",
            entity_type="subscription",
        )
        assert ctx.tenant_id == "tenant-123"
        assert ctx.entity_id == "entity-456"
        assert ctx.entity_type == "subscription"

    def test_command_structure(self) -> None:
        """Command should have kind and payload."""
        cmd = Command(kind="test", payload={"key": "value"})
        assert cmd.kind == "test"
        assert cmd.payload["key"] == "value"

        # Default payload
        cmd_default = Command(kind="test")
        assert cmd_default.payload == {}


class TestEntityWorkflowTemplate:
    """Tests for entity workflow template patterns."""

    def test_concrete_implementation_extends_base(self) -> None:
        """Concrete workflows should extend EntityWorkflowBase."""
        workflow_instance = TestEntityWorkflow()
        assert isinstance(workflow_instance, EntityWorkflowBase)
        assert hasattr(workflow_instance, "run")
        assert hasattr(workflow_instance, "submit")
        assert hasattr(workflow_instance, "complete")
        assert hasattr(workflow_instance, "status")

    def test_concrete_implementation_has_required_methods(self) -> None:
        """Concrete workflows must implement abstract methods."""
        workflow_instance = TestEntityWorkflow()
        assert hasattr(workflow_instance, "_apply")
        assert hasattr(workflow_instance, "_get_state")
        assert callable(workflow_instance._apply)
        assert callable(workflow_instance._get_state)
