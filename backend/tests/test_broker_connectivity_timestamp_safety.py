import math

import pytest

from app.broker_connectivity import BrokerConnectivitySupervisor, ConnectivityState


def test_record_success_without_timestamp_uses_real_clock(monkeypatch):
    monkeypatch.setattr("app.broker_connectivity.time.time", lambda: 1234.5)

    snapshot = BrokerConnectivitySupervisor().record_success()

    assert snapshot.state is ConnectivityState.HEALTHY
    assert snapshot.last_success_at == 1234.5
    assert snapshot.can_trade is True


def test_non_finite_success_timestamp_fails_closed():
    supervisor = BrokerConnectivitySupervisor()

    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="timestamp must be finite"):
            supervisor.success(value)

    assert supervisor.snapshot().state is ConnectivityState.DISCONNECTED
    assert supervisor.snapshot().can_trade is False


def test_non_finite_failure_and_recovery_timestamps_fail_closed():
    supervisor = BrokerConnectivitySupervisor()

    with pytest.raises(ValueError, match="timestamp must be finite"):
        supervisor.failure(math.nan)
    with pytest.raises(ValueError, match="timestamp must be finite"):
        supervisor.begin_recovery(math.inf)

    assert supervisor.snapshot().state is ConnectivityState.DISCONNECTED
    assert supervisor.snapshot().can_trade is False


def test_explicit_zero_timestamp_remains_supported_for_deterministic_callers():
    snapshot = BrokerConnectivitySupervisor().record_success(0.0)

    assert snapshot.state is ConnectivityState.HEALTHY
    assert snapshot.last_success_at == 0.0
