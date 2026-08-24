from app.emergency_halt import EmergencyHaltController
from app.safety_state import SafetyStateStore
from app.startup_execution_state import StartupExecutionState, StartupExecutionStateMachine


def test_shared_controller_halts_execution_state(tmp_path):
    safety = SafetyStateStore(str(tmp_path / 'safety.json'))
    startup = StartupExecutionStateMachine()
    startup.transition(StartupExecutionState.RECOVERING)
    controller = EmergencyHaltController(safety, startup)
    controller.halt('operator emergency stop')
    assert safety.load().trading_halted is True
    assert startup.state == StartupExecutionState.HALTED
    assert controller.is_halted() is True
