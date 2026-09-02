import pytest

from app.brokers.dhan import DhanAdapter


class FakeDhanClient:
    def __init__(self, trades):
        self.trades = trades

    def get_trades(self):
        return self.trades

    def get_trades_for_order(self, order_id):
        return self.trades


def trade(**overrides):
    value = {
        "dhanClientId": "1000000003",
        "orderId": "ORD-1",
        "exchangeTradeId": "TRD-1",
        "tradedQuantity": 2,
        "tradedPrice": 101.25,
    }
    value.update(overrides)
    return value


def adapter(trades):
    instance = DhanAdapter({"access_token": "token", "dhan_client_id": "1000000003"})
    instance.client = FakeDhanClient(trades)
    return instance


def test_order_trades_require_requested_order_identity():
    with pytest.raises(RuntimeError, match="order identity"):
        adapter([trade(orderId="ORD-OTHER")]).get_trades_for_order("ORD-1")


def test_order_trades_reject_duplicate_trade_identity():
    with pytest.raises(RuntimeError, match="duplicate trade identity"):
        adapter([trade(), trade()]).get_trades_for_order("ORD-1")


def test_order_trades_require_positive_quantity_and_price():
    with pytest.raises(RuntimeError, match="positive traded quantity"):
        adapter([trade(tradedQuantity=0)]).get_trades_for_order("ORD-1")
    with pytest.raises(RuntimeError, match="positive traded price"):
        adapter([trade(tradedPrice=0)]).get_trades_for_order("ORD-1")


def test_order_trades_require_configured_account_identity():
    with pytest.raises(RuntimeError, match="account identity"):
        adapter([trade(dhanClientId="OTHER")]).get_trades_for_order("ORD-1")


def test_order_trades_accept_valid_authoritative_records():
    records = adapter([trade(), trade(exchangeTradeId="TRD-2", tradedQuantity=3, tradedPrice=102.0)]).get_trades_for_order("ORD-1")
    assert [record["exchangeTradeId"] for record in records] == ["TRD-1", "TRD-2"]
