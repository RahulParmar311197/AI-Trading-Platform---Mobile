import pytest

from app.broker_connectivity import BrokerConnectionState, BrokerConnectivitySupervisor


def test_starts_fail_closed():
    supervisor = BrokerConnectivitySupervisor()
    snapshot = supervisor.snapshot()
    assert snapshot.state is BrokerConnectionState.DISCONNECTED
    assert snapshot.can_trade is False


def test_success_recovers_and_enables_trading():
    supervisor = BrokerConnectivitySupervisor(max_failures=2)
    supervisor.failure(10)
    snapshot = supervisor.success(20)
    assert snapshot.state is BrokerConnectionState.HEALTHY
    assert snapshot.can_trade is True
    assert snapshot.failures == 0
    assert snapshot.last_success_at == 20


def test_repeated_failures_disconnect():
    supervisor = BrokerConnectivitySupervisor(max_failures=2, base_backoff_seconds=2)
    degraded = supervisor.failure(10)
    disconnected = supervisor.failure(12)
    assert degraded.state is BrokerConnectionState.DEGRADED
    assert disconnected.state is BrokerConnectionState.DISCONNECTED
    assert disconnected.can_trade is False
    assert disconnected.next_retry_at == 16


def test_backoff_is_capped_and_recovery_is_gated():
    supervisor = BrokerConnectivitySupervisor(max_failures=1, base_backoff_seconds=2, max_backoff_seconds=5)
    snapshot = supervisor.failure(10)
    assert snapshot.next_retry_at == 12
    waiting = supervisor.begin_recovery(11)
    assert waiting.state is BrokerConnectionState.DISCONNECTED
    recovering = supervisor.begin_recovery(12)
    assert recovering.state is BrokerConnectionState.RECOVERING
    assert recovering.can_trade is False


def test_invalid_configuration_rejected():
    with pytest.raises(ValueError):
        BrokerConnectivitySupervisor(max_failures=0)
