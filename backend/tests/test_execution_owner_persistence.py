from pathlib import Path

from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle


def test_execution_owner_survives_restart(tmp_path: Path):
    path = tmp_path / "execution_state.json"
    store = ExecutionStateStore(str(path))

    lifecycle = OrderLifecycle()
    lifecycle.create("ABC", "NIFTY", "BUY", 2, owner_user_id=42, execution_id="EXEC-1")
    store.save(lifecycle)

    restored = OrderLifecycle()
    assert store.load(restored) is True
    assert restored.orders["ABC"].owner_user_id == 42
    assert restored.orders["ABC"].execution_id == "EXEC-1"


def test_legacy_execution_state_without_owner_remains_loadable(tmp_path: Path):
    path = tmp_path / "execution_state.json"
    path.write_text(
        '{"schema_version": 2, "orders": {"ABC": {'
        '"order_id":"ABC","symbol":"NIFTY","side":"BUY","quantity":1,'
        '"status":"CREATED","filled_quantity":0,"average_fill_price":null,'
        '"applied_fill_quantity":0,"applied_fill_value":0,"broker_order_id":null,'
        '"execution_id":null,"order_type":"MARKET","requested_price":null,"stop":null,"target":null,'
        '"security_id":"","exchange_segment":"NSE_EQ","product_type":"CNC","validity":"DAY",' 
        '"trigger_price":null,"risk_amount":null,"risk_source":null,"risk_confidence":null,"risk_reason":null,'
        '"created_at":"2026-08-24T00:00:00+00:00","updated_at":"2026-08-24T00:00:00+00:00"}},'
        '"positions":{},"realized_pnl_by_symbol":{},"realized_pnl_by_day":{}}',
        encoding="utf-8",
    )

    restored = OrderLifecycle()
    assert ExecutionStateStore(str(path)).load(restored) is True
    assert restored.orders["ABC"].owner_user_id is None
