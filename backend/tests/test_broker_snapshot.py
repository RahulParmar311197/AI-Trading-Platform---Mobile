from app.broker_snapshot import dhan_snapshot, map_dhan_order, map_dhan_position


def test_dhan_order_mapping():
    mapped = map_dhan_order({"orderId": 123, "correlationId": "abc", "orderStatus": "TRADED"})
    assert mapped == {"broker_order_id": "123", "client_order_id": "abc", "status": "TRADED"}


def test_dhan_position_mapping():
    mapped = map_dhan_position({"tradingSymbol": "NIFTY", "netQty": "50"})
    assert mapped == {"symbol": "NIFTY", "quantity": 50.0}


def test_snapshot_maps_orders_and_positions():
    snapshot = dhan_snapshot(
        [{"orderId": "1", "correlationId": "c1", "orderStatus": "PENDING"}],
        [{"tradingSymbol": "NIFTY", "netQty": 10}],
    )
    assert snapshot.orders[0]["broker_order_id"] == "1"
    assert snapshot.positions[0]["quantity"] == 10.0
