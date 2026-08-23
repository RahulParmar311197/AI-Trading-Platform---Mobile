from app.dhan_adapter import DhanAdapter, DhanConfig


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeTransport:
    def __init__(self):
        self.calls = []

    def get(self, url, headers):
        self.calls.append(("GET", url, headers))
        if url.endswith("/orders"):
            return FakeResponse([{"orderId": "O-1", "correlationId": "C-1", "orderStatus": "TRADED"}])
        if url.endswith("/positions"):
            return FakeResponse([{"tradingSymbol": "NIFTY", "netQty": 50}])
        raise AssertionError(url)


def test_dhan_snapshot_reads_and_maps_orders_and_positions():
    transport = FakeTransport()
    adapter = DhanAdapter(
        DhanConfig("client", "token", live_enabled=True), transport=transport
    )

    snapshot = adapter.get_snapshot()

    assert snapshot.orders == [{"broker_order_id": "O-1", "client_order_id": "C-1", "status": "TRADED"}]
    assert snapshot.positions == [{"symbol": "NIFTY", "quantity": 50.0}]
    assert [call[1].split("/v2")[-1] for call in transport.calls] == ["/orders", "/positions"]
    assert all(call[2]["access-token"] == "token" for call in transport.calls)


def test_dhan_snapshot_never_calls_transport_when_live_disabled():
    adapter = DhanAdapter(DhanConfig("client", "token", live_enabled=False), transport=FakeTransport())
    try:
        adapter.get_snapshot()
    except RuntimeError as exc:
        assert "DHAN_LIVE_ENABLED is false" in str(exc)
    else:
        raise AssertionError("expected live execution guard")
