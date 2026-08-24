import json
import pytest

from app.execution_persistence import ExecutionStateStore, EXECUTION_STATE_SCHEMA_VERSION
from app.order_lifecycle import OrderLifecycle


def test_legacy_state_migrates_execution_id(tmp_path):
    path = tmp_path / 'execution.json'
    legacy = {
        'orders': {'o1': {'order_id':'o1','symbol':'NIFTY','side':'BUY','quantity':1,'status':'FILLED','filled_quantity':1,'average_fill_price':100,'applied_fill_quantity':1,'applied_fill_value':100,'broker_order_id':'b1','order_type':'MARKET','requested_price':None,'stop':None,'target':None,'security_id':'','exchange_segment':'NSE_EQ','product_type':'CNC','validity':'DAY','trigger_price':None,'risk_amount':None,'risk_source':None,'risk_confidence':None,'risk_reason':None,'created_at':'2026-08-24T00:00:00+00:00','updated_at':'2026-08-24T00:00:00+00:00'}},
        'positions': {}, 'realized_pnl_by_symbol': {}, 'realized_pnl_by_day': {}
    }
    path.write_text(json.dumps(legacy))
    lifecycle = OrderLifecycle()
    assert ExecutionStateStore(str(path)).load(lifecycle)
    assert lifecycle.orders['o1'].execution_id is None
    assert json.loads(path.read_text())['schema_version'] == EXECUTION_STATE_SCHEMA_VERSION


def test_future_schema_fails_closed(tmp_path):
    path = tmp_path / 'execution.json'
    path.write_text(json.dumps({'schema_version': EXECUTION_STATE_SCHEMA_VERSION + 1, 'orders': {}, 'positions': {}}))
    with pytest.raises(RuntimeError, match='unreadable'):
        ExecutionStateStore(str(path)).load(OrderLifecycle())
