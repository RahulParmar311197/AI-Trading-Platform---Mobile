import pytest

from app.broker_adapter import BrokerOrderRequest, normalize_broker_update


def request():
    return BrokerOrderRequest(client_order_id="c1", symbol="NIFTY", side="BUY", quantity=10)


def test_normalizes_valid_update_against_request():
    result = normalize_broker_update({"order_id":"u1","status":"COMPLETE","client_order_id":"c1","symbol":"nifty","side":"buy","quantity":10,"filled_quantity":10,"average_price":101}, expected=request())
    assert result.status == "FILLED"
    assert result.filled_quantity == 10
    assert result.average_price == 101


@pytest.mark.parametrize("field,value", [("client_order_id","other"),("symbol","BANKNIFTY"),("side","SELL")])
def test_rejects_identity_mismatch(field, value):
    data={"order_id":"u1","status":"NEW", "quantity":10, field:value}
    with pytest.raises(ValueError):
        normalize_broker_update(data, expected=request())


def test_rejects_fill_without_average_price():
    with pytest.raises(ValueError, match="average_price"):
        normalize_broker_update({"order_id":"u1","status":"FILLED","quantity":10,"filled_quantity":10})


def test_rejects_filled_quantity_above_order_quantity():
    with pytest.raises(ValueError, match="exceeds"):
        normalize_broker_update({"order_id":"u1","status":"FILLED","quantity":10,"filled_quantity":11,"average_price":100})
