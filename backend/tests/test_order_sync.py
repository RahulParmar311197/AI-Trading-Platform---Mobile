import pytest

from app.order_sync import CanonicalOrderStatus, from_dhan_postback, normalize_status


def test_dhan_traded_maps_to_filled():
    update = from_dhan_postback({"orderId": "1", "orderStatus": "TRADED", "quantity": 10, "filled_qty": 10, "price": 101})
    assert update.status is CanonicalOrderStatus.FILLED
    assert update.filled_quantity == 10
    assert update.average_price == 101


def test_partial_fill_is_detected():
    assert normalize_status("PENDING", 3, 10) is CanonicalOrderStatus.PARTIALLY_FILLED


def test_rejection_details_are_preserved():
    update = from_dhan_postback({"orderId": "2", "orderStatus": "REJECTED", "quantity": 1, "filled_qty": 0, "omsErrorCode": "E1", "omsErrorDescription": "blocked"})
    assert update.status is CanonicalOrderStatus.REJECTED
    assert update.error_code == "E1"
    assert update.error_message == "blocked"


def test_missing_order_id_is_rejected():
    with pytest.raises(ValueError):
        from_dhan_postback({"orderStatus": "PENDING"})


def test_invalid_fill_is_rejected():
    with pytest.raises(ValueError):
        from_dhan_postback({"orderId": "3", "orderStatus": "TRADED", "quantity": 5, "filled_qty": 6})
