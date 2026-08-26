from app.broker_order_snapshot import BrokerOrderSnapshot
from app.upstox_adapter import UpstoxAdapter, UpstoxConfig


class Response:
    status_code = 200

    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


class Transport:
    def __init__(self, body):
        self.body = body

    def request(self, method, url, **kwargs):
        return Response(self.body)


def test_upstox_order_snapshot_is_complete_for_retrieve_all_list():
    adapter = UpstoxAdapter(
        UpstoxConfig(access_token="token", live_enabled=True),
        transport=Transport({"data": [{"order_id": "U1", "tag": "client-1"}]}),
    )
    snapshot = adapter.get_order_snapshot()
    assert isinstance(snapshot, BrokerOrderSnapshot)
    assert snapshot.complete is True
    assert snapshot.orders == [{"order_id": "U1", "tag": "client-1"}]
    assert snapshot.source == "upstox"


def test_upstox_order_snapshot_fails_closed_for_unexpected_shape():
    adapter = UpstoxAdapter(
        UpstoxConfig(access_token="token", live_enabled=True),
        transport=Transport({"data": {"orders": []}}),
    )
    try:
        adapter.get_order_snapshot()
    except RuntimeError as exc:
        assert "order snapshot" in str(exc)
    else:
        raise AssertionError("unexpected response shape must not be treated as authoritative")
