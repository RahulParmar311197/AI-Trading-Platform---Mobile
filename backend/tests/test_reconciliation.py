from app.reconciliation import reconcile_orders, reconcile_positions


def test_order_missing_and_unknown_are_detected():
    issues = reconcile_orders({"1": {"status": "PENDING"}}, [{"orderId": "2", "orderStatus": "PENDING"}])
    assert {x.kind for x in issues} == {"MISSING_REMOTE_ORDER", "UNKNOWN_REMOTE_ORDER"}


def test_order_status_mismatch_is_detected():
    issues = reconcile_orders({"1": {"status": "PENDING"}}, [{"orderId": "1", "orderStatus": "TRADED"}])
    assert issues[0].kind == "ORDER_STATUS_MISMATCH"


def test_position_quantity_mismatch_is_detected():
    issues = reconcile_positions({"NIFTY": {"quantity": 10}}, [{"tradingSymbol": "NIFTY", "netQty": 5}])
    assert issues[0].kind == "POSITION_QUANTITY_MISMATCH"


def test_matching_state_is_clean():
    assert reconcile_orders({"1": {"status": "PENDING"}}, [{"orderId": "1", "orderStatus": "PENDING"}]) == []
    assert reconcile_positions({"NIFTY": {"quantity": 10}}, [{"tradingSymbol": "NIFTY", "netQty": 10}]) == []
