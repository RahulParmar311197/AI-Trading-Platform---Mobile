import pytest

from app.upstox_adapter import UpstoxAdapter, UpstoxConfig


class Response:
    status_code = 200

    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class Transport:
    def __init__(self, payload):
        self.payload = payload

    def request(self, method, url, **kwargs):
        return Response(self.payload)


def config():
    return UpstoxConfig(
        "token",
        live_enabled=True,
        broker_account_id="42",
        broker_route="upstox:account:42",
        broker_route_generation="account:42:v1",
    )


def test_history_binds_configured_identity_when_upstox_record_omits_scope():
    transport = Transport({"data": [{"tag": "c1", "order_id": "U1", "status": "complete"}]})
    result = UpstoxAdapter(config(), transport).find_order_by_client_id("c1")
    assert result["broker_account_id"] == "42"
    assert result["broker_route"] == "upstox:account:42"
    assert result["broker_route_generation"] == "account:42:v1"


def test_history_rejects_contradictory_account_identity():
    transport = Transport({"data": [{"tag": "c1", "order_id": "U1", "status": "complete", "broker_account_id": "99"}]})
    with pytest.raises(RuntimeError, match="broker_account_id does not match configured route"):
        UpstoxAdapter(config(), transport).find_order_by_client_id("c1")


def test_history_rejects_contradictory_route_identity():
    transport = Transport({"data": [{"tag": "c1", "order_id": "U1", "status": "complete", "broker_route": "upstox:account:99"}]})
    with pytest.raises(RuntimeError, match="broker_route does not match configured route"):
        UpstoxAdapter(config(), transport).find_order_by_client_id("c1")


def test_history_rejects_stale_route_generation():
    transport = Transport({"data": [{"tag": "c1", "order_id": "U1", "status": "complete", "broker_route_generation": "account:42:v0"}]})
    with pytest.raises(RuntimeError, match="broker_route_generation does not match configured route"):
        UpstoxAdapter(config(), transport).find_order_by_client_id("c1")


def test_order_snapshot_binds_configured_identity_for_reconciliation():
    transport = Transport({"data": [{"tag": "c1", "order_id": "U1", "status": "open"}]})
    snapshot = UpstoxAdapter(config(), transport).get_order_snapshot()
    assert snapshot.complete is True
    assert snapshot.orders[0]["broker_account_id"] == "42"
    assert snapshot.orders[0]["broker_route"] == "upstox:account:42"
    assert snapshot.orders[0]["broker_route_generation"] == "account:42:v1"
