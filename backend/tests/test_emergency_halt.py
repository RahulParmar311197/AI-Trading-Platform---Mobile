import pytest

from app.emergency_halt import EmergencyHaltController
from app.safety_state import SafetyStateStore
from app.startup_execution_state import StartupExecutionState, StartupExecutionStateMachine


def test_halt_persists_and_locks_startup(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    startup = StartupExecutionStateMachine()
    startup.transition(StartupExecutionState.RECOVERING)
    controller = EmergencyHaltController(store, startup)

    result = controller.halt("manual emergency stop")

    assert result.halted
    assert controller.is_halted()
    assert startup.state == StartupExecutionState.HALTED
    assert store.load().halt_reason == "manual emergency stop"


def test_persisted_halt_survives_new_controller(tmp_path):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    startup = StartupExecutionStateMachine()
    startup.transition(StartupExecutionState.RECOVERING)
    EmergencyHaltController(store, startup).halt("broker anomaly")

    new_startup = StartupExecutionStateMachine()
    controller = EmergencyHaltController(SafetyStateStore(str(tmp_path / "safety.json")), new_startup)
    assert controller.is_halted()
    with pytest.raises(RuntimeError, match="TRADING_HALTED"):
        controller.require_clear()
