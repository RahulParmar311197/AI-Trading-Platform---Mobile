from types import SimpleNamespace

from app.order_execution_service import OrderExecutionService
from app.order_lifecycle import OrderLifecycle
from app.execution_persistence import ExecutionStateStore
from app.startup_execution_state import StartupExecutionStateMachine, StartupExecutionState
from app.safety_state import SafetyStateStore
from app.trading_audit import TradingAuditLog


def test_execution_result_contains_correlation_id_when_blocked(tmp_path):
    audit = TradingAuditLog(str(tmp_path / 'audit.jsonl'))
    startup = StartupExecutionStateMachine(audit)
    safety = SafetyStateStore(str(tmp_path / 'safety.json'))
    service = OrderExecutionService(object(), OrderLifecycle(), ExecutionStateStore(str(tmp_path / 'execution.json')), safety_state_store=safety, startup_state=startup, audit_log=audit)
    request = SimpleNamespace(client_order_id='OID-1')
    result = service.submit(request)
    assert result.execution_id
    assert result.status == 'REJECTED'
