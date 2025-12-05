"""Unit tests for AuditService."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.app.core.audit_context import AuditContext
from src.app.models.public import AuditAction, AuditStatus
from src.app.services.audit_service import AuditService


@pytest.fixture
def mock_audit_repo() -> MagicMock:
    """Create mock audit repository."""
    repo = MagicMock()
    repo.add = MagicMock()
    return repo


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create mock database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def tenant_id():
    """Create a test tenant ID."""
    return uuid4()


@pytest.fixture
def audit_service(mock_audit_repo, mock_session, tenant_id) -> AuditService:
    """Create AuditService with mocks."""
    return AuditService(mock_audit_repo, mock_session, tenant_id)


class TestLogAction:
    """Tests for log_action method."""

    async def test_log_action_creates_audit_log(self, audit_service, mock_audit_repo, mock_session):
        """log_action should create an AuditLog entry."""
        result = await audit_service.log_action(
            action=AuditAction.USER_LOGIN,
            entity_type="user",
        )

        assert result is not None
        mock_audit_repo.add.assert_called_once()
        mock_session.commit.assert_called_once()

    async def test_log_action_sets_tenant_id(self, audit_service, mock_audit_repo, tenant_id):
        """log_action should set the tenant_id from service context."""
        await audit_service.log_action(
            action=AuditAction.USER_LOGIN,
            entity_type="user",
        )

        call_args = mock_audit_repo.add.call_args[0][0]
        assert call_args.tenant_id == tenant_id

    async def test_log_action_with_user_id(self, audit_service, mock_audit_repo):
        """log_action should accept user_id parameter."""
        user_id = uuid4()

        await audit_service.log_action(
            action=AuditAction.USER_LOGIN,
            entity_type="user",
            user_id=user_id,
        )

        call_args = mock_audit_repo.add.call_args[0][0]
        assert call_args.user_id == user_id

    async def test_log_action_with_entity_id(self, audit_service, mock_audit_repo):
        """log_action should accept entity_id parameter."""
        entity_id = uuid4()

        await audit_service.log_action(
            action=AuditAction.TENANT_DELETE,
            entity_type="tenant",
            entity_id=entity_id,
        )

        call_args = mock_audit_repo.add.call_args[0][0]
        assert call_args.entity_id == entity_id

    async def test_log_action_with_changes(self, audit_service, mock_audit_repo):
        """log_action should accept changes dictionary."""
        changes = {"name": {"old": "Old Name", "new": "New Name"}}

        await audit_service.log_action(
            action=AuditAction.TENANT_UPDATE,
            entity_type="tenant",
            changes=changes,
        )

        call_args = mock_audit_repo.add.call_args[0][0]
        assert call_args.changes == changes

    async def test_log_action_with_failure_status(self, audit_service, mock_audit_repo):
        """log_action should accept failure status."""
        await audit_service.log_action(
            action=AuditAction.USER_LOGIN,
            entity_type="user",
            status=AuditStatus.FAILURE,
            error_message="Invalid credentials",
        )

        call_args = mock_audit_repo.add.call_args[0][0]
        assert call_args.status == "failure"
        assert call_args.error_message == "Invalid credentials"

    async def test_log_action_truncates_long_error_message(self, audit_service, mock_audit_repo):
        """log_action should truncate error messages over 1000 chars."""
        long_error = "x" * 2000

        await audit_service.log_action(
            action=AuditAction.USER_LOGIN,
            entity_type="user",
            status=AuditStatus.FAILURE,
            error_message=long_error,
        )

        call_args = mock_audit_repo.add.call_args[0][0]
        assert len(call_args.error_message) == 1000

    @patch("src.app.services.audit_service.get_audit_context")
    async def test_log_action_captures_request_context(
        self, mock_get_context, audit_service, mock_audit_repo
    ):
        """log_action should capture IP, user agent, and request_id from context."""
        mock_get_context.return_value = AuditContext(
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            request_id="abc-123",
        )

        await audit_service.log_action(
            action=AuditAction.USER_LOGIN,
            entity_type="user",
        )

        call_args = mock_audit_repo.add.call_args[0][0]
        assert call_args.ip_address == "192.168.1.1"
        assert call_args.user_agent == "Mozilla/5.0"
        assert call_args.request_id == "abc-123"

    @patch("src.app.services.audit_service.get_audit_context")
    async def test_log_action_handles_no_context(
        self, mock_get_context, audit_service, mock_audit_repo
    ):
        """log_action should handle missing audit context gracefully."""
        mock_get_context.return_value = None

        result = await audit_service.log_action(
            action=AuditAction.USER_LOGIN,
            entity_type="user",
        )

        assert result is not None
        call_args = mock_audit_repo.add.call_args[0][0]
        assert call_args.ip_address is None
        assert call_args.user_agent is None
        assert call_args.request_id is None

    async def test_log_action_accepts_string_action(self, audit_service, mock_audit_repo):
        """log_action should accept string action values."""
        await audit_service.log_action(
            action="custom.action",
            entity_type="custom",
        )

        call_args = mock_audit_repo.add.call_args[0][0]
        assert call_args.action == "custom.action"

    async def test_log_action_fire_and_forget_on_error(self, audit_service, mock_session):
        """log_action should not raise on database errors (fire-and-forget)."""
        mock_session.commit.side_effect = Exception("DB Error")

        # Should not raise
        result = await audit_service.log_action(
            action=AuditAction.USER_LOGIN,
            entity_type="user",
        )

        assert result is None
        mock_session.rollback.assert_called_once()


class TestLogSuccess:
    """Tests for log_success convenience method."""

    async def test_log_success_sets_success_status(self, audit_service, mock_audit_repo):
        """log_success should set status to success."""
        await audit_service.log_success(
            action=AuditAction.USER_LOGIN,
            entity_type="user",
        )

        call_args = mock_audit_repo.add.call_args[0][0]
        assert call_args.status == "success"


class TestLogFailure:
    """Tests for log_failure convenience method."""

    async def test_log_failure_sets_failure_status(self, audit_service, mock_audit_repo):
        """log_failure should set status to failure."""
        await audit_service.log_failure(
            action=AuditAction.USER_LOGIN,
            entity_type="user",
            error_message="Invalid credentials",
        )

        call_args = mock_audit_repo.add.call_args[0][0]
        assert call_args.status == "failure"
        assert call_args.error_message == "Invalid credentials"


class TestListLogs:
    """Tests for list_logs method."""

    async def test_list_logs_calls_repository(self, audit_service, mock_audit_repo, tenant_id):
        """list_logs should call repository with correct parameters."""
        mock_audit_repo.list_by_tenant = AsyncMock(return_value=([], None, False))

        await audit_service.list_logs(
            cursor="abc",
            limit=25,
            action="user.login",
            user_id=uuid4(),
        )

        mock_audit_repo.list_by_tenant.assert_called_once()
        call_kwargs = mock_audit_repo.list_by_tenant.call_args[1]
        assert call_kwargs["tenant_id"] == tenant_id
        assert call_kwargs["cursor"] == "abc"
        assert call_kwargs["limit"] == 25
        assert call_kwargs["action"] == "user.login"


class TestListEntityHistory:
    """Tests for list_entity_history method."""

    async def test_list_entity_history_calls_repository(self, audit_service, mock_audit_repo):
        """list_entity_history should call repository with correct parameters."""
        mock_audit_repo.list_by_entity = AsyncMock(return_value=([], None, False))
        entity_id = uuid4()

        await audit_service.list_entity_history(
            entity_type="tenant",
            entity_id=entity_id,
            cursor="def",
            limit=30,
        )

        mock_audit_repo.list_by_entity.assert_called_once()
        call_kwargs = mock_audit_repo.list_by_entity.call_args[1]
        assert call_kwargs["entity_type"] == "tenant"
        assert call_kwargs["entity_id"] == entity_id
        assert call_kwargs["cursor"] == "def"
        assert call_kwargs["limit"] == 30
