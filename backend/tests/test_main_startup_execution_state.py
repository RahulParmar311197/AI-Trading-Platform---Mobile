import pytest

from app.startup_execution_state import StartupExecutionState, StartupExecutionStateMachine


def test_bootstrap_state_sequence_is_authoritative():
    state = StartupExecutionStateMachine()
    assert not state.execution_allowed
    state.transition(StartupExecutionState.RECOVERING)
    state.transition(StartupExecutionState.BROKER_RECONCILED)
    state.transition(StartupExecutionState.PORTFOLIO_RECONCILED)
    state.transition(StartupExecutionState.RISK_READY)
    state.transition(StartupExecutionState.READY)
    assert state.execution_allowed


def test_bootstrap_failure_never_reports_ready():
    state = StartupExecutionStateMachine()
    state.transition(StartupExecutionState.RECOVERING)
    state.fail("portfolio reconciliation failed")
    assert state.state == StartupExecutionState.FAILED
    assert not state.execution_allowed
    with pytest.raises(RuntimeError):
        state.require_ready()
