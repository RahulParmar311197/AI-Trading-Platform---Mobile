import pytest

from app.startup_execution_state import StartupExecutionState, StartupExecutionStateMachine


def test_happy_path_reaches_ready_only_in_order():
    machine = StartupExecutionStateMachine()
    for state in (
        StartupExecutionState.RECOVERING,
        StartupExecutionState.BROKER_RECONCILED,
        StartupExecutionState.PORTFOLIO_RECONCILED,
        StartupExecutionState.RISK_READY,
        StartupExecutionState.READY,
    ):
        machine.transition(state)
    assert machine.execution_allowed


def test_invalid_transition_is_rejected():
    machine = StartupExecutionStateMachine()
    with pytest.raises(RuntimeError):
        machine.transition(StartupExecutionState.READY)
    assert not machine.execution_allowed


def test_failure_is_fail_closed():
    machine = StartupExecutionStateMachine()
    machine.transition(StartupExecutionState.RECOVERING)
    machine.fail("broker reconciliation failed")
    assert machine.state == StartupExecutionState.FAILED
    assert not machine.execution_allowed
    assert machine.status.reason == "broker reconciliation failed"


def test_halted_state_requires_explicit_recovery():
    machine = StartupExecutionStateMachine()
    machine.halt("portfolio mismatch")
    assert not machine.execution_allowed
    with pytest.raises(RuntimeError):
        machine.transition(StartupExecutionState.READY)
    machine.transition(StartupExecutionState.RECOVERING)
    assert machine.state == StartupExecutionState.RECOVERING
