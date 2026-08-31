import pytest

from app.broker_adapter import BrokerOrderRequest, normalize_broker_update
from app.dhan_adapter import DhanAdapter, DhanConfig


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected HTTP {self.status_code}")


class FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


def _request():
    return BrokerOrderRequest(
        client_order_id="manual-123",
        symbol="NIFTY",
        side="BUY",
        quantity=2,
        security_id="12345",
        broker_account_id="acct-1",
        broker_route="dhan-primary",
        broker_route_generation="gen-7",
    )


def _adapter(payload):
    return DhanAdapter(
        DhanConfig(client_id="acct-1", access_token="token", live_enabled=True),
        transport=FakeTransport(payload),
    )


def test_dhan_submission_result_is_canonical_and_identity_complete():
    adapter = _adapter({"orderId": "D-42", "orderStatus": "TRANSIT"})

    update = adapter.submit_order(_request())

    assert update.order_id == "D-42"
    assert update.status == "NEW"
    assert update.client_order_id == "manual-123"
    assert update.symbol == "NIFTY"
    assert update.side == "BUY"
    assert update.quantity == 2
    assert update.broker_account_id == "acct-1"
    assert update.broker_route == "dhan-primary"
    assert update.broker_route_generation == "gen-7"

    canonical = normalize_broker_update(update, expected=_request())
    assert canonical.status == "NEW"
    assert canonical.broker_account_id == "acct-1"
    assert canonical.broker_route == "dhan-primary"


def test_dhan_rejection_is_preserved_as_terminal_submission_result():
    adapter = _adapter({"orderId": "D-43", "orderStatus": "REJECTED"})

    update = adapter.submit_order(_request())

    assert update.status == "REJECTED"
    assert update.filled_quantity is None
    normalize_broker_update(update, expected=_request())


def test_dhan_filled_submission_requires_authoritative_fill_details():
    adapter = _adapter(
        {
            "orderId": "D-44",
            "orderStatus": "TRADED",
            "filledQty": 2,
            "averageTradedPrice": 225.5,
        }
    )

    update = adapter.submit_order(_request())

    assert update.status == "FILLED"
    assert update.filled_quantity == 2
    assert update.average_price == 225.5
    normalize_broker_update(update, expected=_request())


def test_dhan_filled_submission_fails_closed_without_fill_price():
    adapter = _adapter({"orderId": "D-45", "orderStatus": "TRADED", "filledQty": 2})

    with pytest.raises(ValueError, match="non-zero broker fill requires average_price"):
        adapter.submit_order(_request())
