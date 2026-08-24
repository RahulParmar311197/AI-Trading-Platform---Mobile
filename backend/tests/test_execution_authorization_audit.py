import json

from types import SimpleNamespace
from app.execution_authorization import ExecutionAuthorization
from app.safety_state import SafetyStateStore
from app.trading_audit import TradingAuditLog


def test_authorization_audit_records_rejection(tmp_path):
    safety = SafetyStateStore(str(tmp_path / 'safety.json'))
    audit = TradingAuditLog(str(tmp_path / 'audit.jsonl'))
    safety.halt('operator stop')
    auth = ExecutionAuthorization(safety, audit_log=audit)
    result = auth.check(SimpleNamespace(client_order_id='OID-1'))
    assert not result.allowed
    row = json.loads((tmp_path / 'audit.jsonl').read_text().splitlines()[-1])
    assert row['event_type'] == 'EXECUTION_AUTHORIZATION'
    assert row['metadata']['client_order_id'] == 'OID-1'
    assert row['metadata']['code'] == 'TRADING_HALTED'
