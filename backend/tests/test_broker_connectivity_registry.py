import pytest

from app.broker_connectivity import BrokerConnectionState
from app.broker_connectivity_registry import BrokerConnectivityRegistry


def test_registry_isolated_by_account_and_route():
    registry = BrokerConnectivityRegistry()
    first = registry.get(1, "dhan:account:1")
    second = registry.get(2, "dhan:account:2")

    first.success(10.0)

    assert registry.snapshot(1, "dhan:account:1").state is BrokerConnectionState.HEALTHY
    assert registry.snapshot(2, "dhan:account:2").state is BrokerConnectionState.DISCONNECTED
    assert first is not second


def test_registry_reuses_same_supervisor_for_same_key():
    registry = BrokerConnectivityRegistry()
    assert registry.get(1, "upstox:account:1") is registry.get(1, "upstox:account:1")


def test_registry_preserves_opaque_account_identity():
    registry = BrokerConnectivityRegistry()
    padded = registry.get("001", "upstox")
    numeric = registry.get("1", "upstox")

    assert padded is not numeric
    padded.success(10.0)
    assert registry.snapshot("001", "upstox").state is BrokerConnectionState.HEALTHY
    assert registry.snapshot("1", "upstox").state is BrokerConnectionState.DISCONNECTED


def test_registry_validates_scope():
    registry = BrokerConnectivityRegistry()
    with pytest.raises(ValueError):
        registry.get(0, "dhan:account:0")
    with pytest.raises(ValueError):
        registry.get(None, "dhan:account:none")
    with pytest.raises(ValueError):
        registry.get(1, "")
