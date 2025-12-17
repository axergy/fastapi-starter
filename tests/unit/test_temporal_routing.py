"""Tests for Temporal routing and task queue assignment."""

import pytest

from src.app.temporal.routing import (
    QueueKind,
    TemporalRoute,
    _stable_shard,
    route_for_system_job,
    route_for_tenant,
    task_queue_name,
)

pytestmark = pytest.mark.unit


class TestStableShard:
    """Shard function must be deterministic across processes."""

    def test_same_input_same_shard(self):
        """Same tenant_id always maps to same shard."""
        tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        shard1 = _stable_shard(tenant_id, 32)
        shard2 = _stable_shard(tenant_id, 32)
        assert shard1 == shard2

    def test_different_inputs_distribute(self):
        """Different tenants distribute across shards."""
        tenant_ids = [f"tenant-{i}" for i in range(100)]
        shards = {_stable_shard(tid, 32) for tid in tenant_ids}
        # Should hit at least 20 of 32 shards with 100 tenants
        assert len(shards) >= 20

    def test_shards_one_always_zero(self):
        """With shards=1, always returns 0."""
        assert _stable_shard("any-tenant", 1) == 0

    def test_shards_bounds(self):
        """Shard is always in valid range."""
        for i in range(100):
            shard = _stable_shard(f"tenant-{i}", 64)
            assert 0 <= shard < 64

    def test_deterministic_across_runs(self):
        """Same input produces same shard across multiple calls."""
        tenant_id = "test-tenant-123"
        expected = _stable_shard(tenant_id, 16)
        for _ in range(10):
            assert _stable_shard(tenant_id, 16) == expected

    def test_different_shard_counts(self):
        """Same tenant maps consistently when shard count changes."""
        tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        # These should be different but deterministic
        shard_8 = _stable_shard(tenant_id, 8)
        shard_16 = _stable_shard(tenant_id, 16)
        shard_32 = _stable_shard(tenant_id, 32)

        assert 0 <= shard_8 < 8
        assert 0 <= shard_16 < 16
        assert 0 <= shard_32 < 32


class TestTaskQueueName:
    """Queue name generation tests."""

    def test_format_tenant(self):
        """Queue name follows expected format."""
        name = task_queue_name("saas", QueueKind.TENANT, 5)
        assert name == "saas.tenant.05"

    def test_format_jobs(self):
        """Jobs queue name format."""
        name = task_queue_name("app", QueueKind.JOBS, 0)
        assert name == "app.jobs.00"

    def test_zero_padded(self):
        """Shard is zero-padded to 2 digits."""
        name = task_queue_name("app", QueueKind.TENANT, 3)
        assert ".03" in name

    def test_zero_padded_double_digit(self):
        """Double digit shards are not over-padded."""
        name = task_queue_name("app", QueueKind.TENANT, 15)
        assert name == "app.tenant.15"

    def test_max_shard(self):
        """Maximum shard number (99) is handled."""
        name = task_queue_name("app", QueueKind.JOBS, 99)
        assert name == "app.jobs.99"

    def test_different_prefixes(self):
        """Different prefixes produce different queue names."""
        name1 = task_queue_name("saas", QueueKind.TENANT, 5)
        name2 = task_queue_name("platform", QueueKind.TENANT, 5)
        assert name1 != name2
        assert name1.startswith("saas.")
        assert name2.startswith("platform.")


class TestRouteForTenant:
    """Integration tests for routing function."""

    def test_returns_route(self):
        """Returns valid TemporalRoute."""
        route = route_for_tenant(
            tenant_id="test-tenant",
            namespace="default",
            prefix="saas",
            shards=32,
            kind=QueueKind.TENANT,
        )
        assert route.namespace == "default"
        assert route.task_queue.startswith("saas.tenant.")
        assert route.priority is not None
        assert route.priority.fairness_key == "test-tenant"

    def test_fairness_weight_default(self):
        """Default fairness weight is 1."""
        route = route_for_tenant(
            tenant_id="test",
            namespace="ns",
            prefix="p",
            shards=1,
            kind=QueueKind.TENANT,
        )
        assert route.priority.fairness_weight == 1

    def test_fairness_weight_propagates(self):
        """Fairness weight is set correctly."""
        route = route_for_tenant(
            tenant_id="premium-tenant",
            namespace="default",
            prefix="saas",
            shards=1,
            kind=QueueKind.TENANT,
            fairness_weight=10,
        )
        assert route.priority.fairness_weight == 10

    def test_same_tenant_same_queue(self):
        """Same tenant always routes to same queue."""
        tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        route1 = route_for_tenant(
            tenant_id=tenant_id,
            namespace="default",
            prefix="saas",
            shards=32,
            kind=QueueKind.TENANT,
        )
        route2 = route_for_tenant(
            tenant_id=tenant_id,
            namespace="default",
            prefix="saas",
            shards=32,
            kind=QueueKind.TENANT,
        )
        assert route1.task_queue == route2.task_queue

    def test_different_tenants_can_share_queue(self):
        """Different tenants may share queues due to sharding."""
        # With only 2 shards, some of 100 tenants must collide
        tenant_ids = [f"tenant-{i}" for i in range(100)]
        queues = set()
        for tid in tenant_ids:
            route = route_for_tenant(
                tenant_id=tid,
                namespace="default",
                prefix="saas",
                shards=2,
                kind=QueueKind.TENANT,
            )
            queues.add(route.task_queue)

        # Should have exactly 2 unique queues
        assert len(queues) == 2

    def test_jobs_kind(self):
        """Can route tenants to JOBS queue kind."""
        route = route_for_tenant(
            tenant_id="test-tenant",
            namespace="default",
            prefix="saas",
            shards=8,
            kind=QueueKind.JOBS,
        )
        assert ".jobs." in route.task_queue

    def test_route_is_frozen(self):
        """TemporalRoute is immutable."""
        route = route_for_tenant(
            tenant_id="test",
            namespace="default",
            prefix="saas",
            shards=1,
            kind=QueueKind.TENANT,
        )
        with pytest.raises(AttributeError):
            route.namespace = "changed"  # type: ignore


class TestRouteForSystemJob:
    """System job routing tests."""

    def test_returns_route(self):
        """Returns valid TemporalRoute without priority."""
        route = route_for_system_job(
            namespace="default",
            prefix="saas",
            kind=QueueKind.JOBS,
        )
        assert route.namespace == "default"
        assert route.task_queue == "saas.jobs.00"
        assert route.priority is None

    def test_default_kind_is_jobs(self):
        """Default kind is JOBS."""
        route = route_for_system_job(
            namespace="default",
            prefix="saas",
        )
        assert ".jobs." in route.task_queue

    def test_always_shard_zero(self):
        """System jobs always use shard 00."""
        route = route_for_system_job(
            namespace="default",
            prefix="platform",
            kind=QueueKind.JOBS,
        )
        assert route.task_queue.endswith(".00")

    def test_no_fairness_priority(self):
        """System jobs don't use fairness priority."""
        route = route_for_system_job(
            namespace="default",
            prefix="saas",
        )
        assert route.priority is None

    def test_different_namespaces(self):
        """Different namespaces produce different routes."""
        route1 = route_for_system_job(namespace="prod", prefix="saas")
        route2 = route_for_system_job(namespace="staging", prefix="saas")

        assert route1.namespace != route2.namespace
        assert route1.task_queue == route2.task_queue  # Same queue name

    def test_can_use_tenant_kind(self):
        """Can specify TENANT kind for system jobs if needed."""
        route = route_for_system_job(
            namespace="default",
            prefix="saas",
            kind=QueueKind.TENANT,
        )
        assert route.task_queue == "saas.tenant.00"


class TestQueueKind:
    """Tests for QueueKind enum."""

    def test_tenant_value(self):
        """TENANT kind has correct string value."""
        assert QueueKind.TENANT == "tenant"

    def test_jobs_value(self):
        """JOBS kind has correct string value."""
        assert QueueKind.JOBS == "jobs"

    def test_str_representation(self):
        """String representation is the value."""
        assert str(QueueKind.TENANT) == "tenant"
        assert str(QueueKind.JOBS) == "jobs"

    def test_can_iterate(self):
        """Can iterate over all queue kinds."""
        kinds = list(QueueKind)
        assert QueueKind.TENANT in kinds
        assert QueueKind.JOBS in kinds
        assert len(kinds) == 2


class TestTemporalRoute:
    """Tests for TemporalRoute dataclass."""

    def test_creation_with_priority(self):
        """Can create route with priority."""
        from src.app.temporal.routing import Priority

        priority = Priority(fairness_key="tenant-123", fairness_weight=5)
        route = TemporalRoute(
            namespace="prod",
            task_queue="saas.tenant.05",
            priority=priority,
        )
        assert route.namespace == "prod"
        assert route.task_queue == "saas.tenant.05"
        assert route.priority == priority

    def test_creation_without_priority(self):
        """Can create route without priority."""
        route = TemporalRoute(
            namespace="prod",
            task_queue="saas.jobs.00",
        )
        assert route.priority is None

    def test_equality(self):
        """Two routes with same values are equal."""
        route1 = TemporalRoute(
            namespace="prod",
            task_queue="saas.tenant.05",
        )
        route2 = TemporalRoute(
            namespace="prod",
            task_queue="saas.tenant.05",
        )
        assert route1 == route2

    def test_inequality(self):
        """Routes with different values are not equal."""
        route1 = TemporalRoute(namespace="prod", task_queue="saas.tenant.05")
        route2 = TemporalRoute(namespace="prod", task_queue="saas.tenant.06")
        assert route1 != route2

    def test_hashable(self):
        """TemporalRoute can be used in sets/dicts."""
        route1 = TemporalRoute(namespace="prod", task_queue="saas.tenant.05")
        route2 = TemporalRoute(namespace="prod", task_queue="saas.tenant.06")

        routes = {route1, route2}
        assert len(routes) == 2
        assert route1 in routes
