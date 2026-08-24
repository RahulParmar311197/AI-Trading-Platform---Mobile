from app.app_factory import create_resources
from app.startup_execution_state import StartupExecutionState


def test_resources_expose_one_startup_state_machine():
    resources = create_resources()
    assert resources.startup_execution_state is not None
    assert resources.startup_execution_state.state == StartupExecutionState.LOCKED
    assert not resources.startup_execution_state.execution_allowed


def test_execution_service_can_receive_same_resource_state():
    resources = create_resources()
    assert resources.startup_execution_state is not None
    state = resources.startup_execution_state
    state.transition(StartupExecutionState.RECOVERING)
    state.transition(StartupExecutionState.BROKER_RECONCILED)
    state.transition(StartupExecutionState.PORTFOLIO_RECONCILED)
    state.transition(StartupExecutionState.RISK_READY)
    state.transition(StartupExecutionState.READY)
    assert resources.startup_execution_state is state
    assert resources.startup_execution_state.execution_allowed
