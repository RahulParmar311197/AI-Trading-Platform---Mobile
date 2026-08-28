from app.risk_circuit_observability import ObservableRiskCircuitBreaker
from app.safety_state import SafetyStateStore


def test_risk_circuit_survives_process_recreation(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    first = ObservableRiskCircuitBreaker(safety_store=store)

    first.engage("max_daily_loss")
    assert first.status().blocked is True

    second = ObservableRiskCircuitBreaker(safety_store=store)
    assert second.status().blocked is True
    assert second.status().reason == "max_daily_loss"
    assert second.can_trade() is False


def test_risk_circuit_reset_is_persisted(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    first = ObservableRiskCircuitBreaker(safety_store=store)
    first.engage("stale_data")
    first.reset()

    second = ObservableRiskCircuitBreaker(safety_store=store)
    assert second.status().blocked is False
    assert second.status().reason == ""
    assert second.can_trade() is True


def test_risk_circuit_persistence_preserves_reconciliation_state(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    store.halt("test halt")
    store.engage_risk_circuit("reconciliation_drift")

    state = store.load()
    assert state.trading_halted is True
    assert state.halt_reason == "test halt"
    assert state.risk_circuit_blocked is True
    assert state.risk_circuit_reason == "reconciliation_drift"
