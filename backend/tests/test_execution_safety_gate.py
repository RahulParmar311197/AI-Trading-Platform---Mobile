import pytest

from app.execution_safety_gate import ExecutionSafetyContext, ExecutionSafetyGate, ExecutionBlockReason


@pytest.fixture
def gate():
    return ExecutionSafetyGate()


def ready(**overrides):
    values = dict(emergency_halt=False, reconciliation_ready=True, broker_healthy=True, risk_allowed=True, broker_account_id=1, broker_route="primary")
    values.update(overrides)
    return ExecutionSafetyContext(**values)


def test_ready_context_is_authorized(gate):
    assert gate.authorize(ready()).allowed is True


@pytest.mark.parametrize("override,reason", [
    ({"emergency_halt": True}, ExecutionBlockReason.EMERGENCY_HALT),
    ({"reconciliation_ready": False}, ExecutionBlockReason.RECONCILIATION_NOT_READY),
    ({"broker_healthy": False}, ExecutionBlockReason.BROKER_UNHEALTHY),
    ({"risk_allowed": False}, ExecutionBlockReason.RISK_LIMIT_BREACH),
    ({"broker_account_id": None}, ExecutionBlockReason.INVALID_SCOPE),
    ({"broker_route": ""}, ExecutionBlockReason.INVALID_SCOPE),
])
def test_any_safety_failure_blocks_execution(gate, override, reason):
    decision = gate.authorize(ready(**override))
    assert decision.allowed is False
    assert decision.reason == reason


def test_emergency_halt_has_precedence(gate):
    decision = gate.authorize(ready(emergency_halt=True, broker_healthy=False, risk_allowed=False))
    assert decision.reason == ExecutionBlockReason.EMERGENCY_HALT
