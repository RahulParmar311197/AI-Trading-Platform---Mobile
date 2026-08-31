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


def test_dhan_submission_result_is_canonical_and_identity_complete():
    transport = FakeTransport({"orderId": "D-42", "orderStatus": "TRANSIT"})
    adapter = DhanAdapter(
        DhanConfig(client_id="acct-1", access_token="token", live_enabled=True),
        transport=transport,
    )

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
    transport = FakeTransport({"orderId": "D-43", "orderStatus": "REJECTED"})
    adapter = DhanAdapter(
        DhanConfig(client_id="acct-1", access_token="token", live_enabled=True),
        transport=transport,
    )

    update = adapter.submit_order(_request())

    assert update.status == "REJECTED"
    assert update.filled_quantity is None
    normalize_broker_update(update, expected=_request())
