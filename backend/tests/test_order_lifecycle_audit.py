import json

from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.trading_audit import TradingAuditLog


def test_order_create_fill_and_state_are_audited(tmp_path):
    path = tmp_path / 'audit.jsonl'
    audit = TradingAuditLog(str(path))
    lifecycle = OrderLifecycle(audit)
    lifecycle.create('o1', 'NIFTY', 'BUY', 2)
    lifecycle.transition('o1', OrderStatus.SUBMISSION_INTENT)
    lifecycle.transition('o1', OrderStatus.SUBMITTED)
    lifecycle.apply_fill('o1', 2, 100.0, fill_id='fill-1')

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    types = [row['event_type'] for row in rows]
    assert 'ORDER_CREATED' in types
    assert 'ORDER_STATE_CHANGE' in types
    assert 'ORDER_FILL' in types
