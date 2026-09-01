import pytest

from app.broker_adapter import BrokerOrderRequest
from app.upstox_adapter import UpstoxAdapter, UpstoxConfig


class Response:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")

    def json(self):
        return self.data


class Transport:
    def __init__(self, response):
        self.response = response

    def request(self, method, url, **kwargs):
        return self.response


def adapter(response):
    return UpstoxAdapter(
        UpstoxConfig("token", live_enabled=True),
        Transport(response),
    )


def test_order_snapshot_rejects_non_mapping_records():
    with pytest.raises(RuntimeError, match="authoritative"):
        adapter(Response({"data": [{"order_id": "U1"}, "malformed"]})).get_order_snapshot()


def test_position_snapshot_rejects_non_mapping_records():
    with pytest.raises(RuntimeError, match="authoritative"):
        adapter(Response({"data": [{"symbol": "NIFTY", "quantity": 1}, 42]})).get_position_snapshot()


def test_order_history_rejects_non_mapping_records():
    with pytest.raises(RuntimeError, match="authoritative"):
        adapter(Response({"data": [{"tag": "client-1", "order_id": "U1"}, "malformed"]})).find_order_by_client_id("client-1")


def test_account_response_rejects_non_mapping_payload():
    with pytest.raises(RuntimeError, match="authoritative"):
        adapter(Response({"data": []})).get_account()
