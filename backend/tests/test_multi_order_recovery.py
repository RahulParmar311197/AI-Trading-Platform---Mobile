import pytest

from app.order_execution_service import OrderExecutionService


def test_multi_order_aggregation_sums_fills_and_calculates_weighted_average():
    status, filled, average, ids = OrderExecutionService._aggregate_recovered_orders(
        [
            {"order_id": "child-a", "status": "PART_TRADED", "filled_quantity": 6, "average_price": 100},
            {"order_id": "child-b", "status": "COMPLETE", "filled_quantity": 4, "average_price": 110},
        ],
        10,
    )
    assert status == "FILLED"
    assert filled == 10
    assert average == 104
    assert ids == "child-a,child-b"


def test_multi_order_duplicate_child_is_rejected():
    with pytest.raises(RuntimeError, match="duplicate broker child order id"):
        OrderExecutionService._aggregate_recovered_orders(
            [
                {"order_id": "child-a", "status": "COMPLETE", "filled_quantity": 5, "average_price": 100},
                {"order_id": "child-a", "status": "COMPLETE", "filled_quantity": 5, "average_price": 100},
            ],
            10,
        )


def test_multi_order_overfill_is_rejected():
    with pytest.raises(RuntimeError, match="exceeds requested quantity"):
        OrderExecutionService._aggregate_recovered_orders(
            [
                {"order_id": "child-a", "status": "COMPLETE", "filled_quantity": 6, "average_price": 100},
                {"order_id": "child-b", "status": "COMPLETE", "filled_quantity": 5, "average_price": 100},
            ],
            10,
        )


def test_multi_order_missing_price_for_fill_is_rejected():
    with pytest.raises(RuntimeError, match="missing average fill price"):
        OrderExecutionService._aggregate_recovered_orders(
            [{"order_id": "child-a", "status": "COMPLETE", "filled_quantity": 10}],
            10,
        )
