import pytest

from app.broker_adapter import BrokerOrderRequest
from app.upstox_adapter import UpstoxAdapter, UpstoxConfig


class Response:
    def __init__(self, body, status_code=200): self._body=body; self.status_code=status_code
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(f"HTTP {self.status_code}")
    def json(self): return self._body


class Transport:
    def __init__(self, body): self.body=body; self.calls=[]
    def request(self, method, url, **kwargs): self.calls.append((method,url,kwargs)); return Response(self.body)


def make(body):
    transport=Transport(body)
    adapter=UpstoxAdapter(UpstoxConfig(access_token="token",live_enabled=True), transport=transport)
    return adapter, transport


def req(): return BrokerOrderRequest(client_order_id="c1",symbol="NIFTY",side="BUY",quantity=10,security_id="NSE_FO|1")


def test_submit_returns_canonical_new_update():
    adapter,_=make({"data":{"order_ids":["u1"]}})
    result=adapter.submit_order(req())
    assert result.order_id == "u1"
    assert result.status == "NEW"
    assert result.client_order_id == "c1"


def test_submit_rejects_missing_identity():
    adapter,_=make({"data":{"order_ids":[]}})
    with pytest.raises(RuntimeError, match="order id"):
        adapter.submit_order(req())


def test_submit_rejects_multiple_child_ids():
    adapter,_=make({"data":{"order_ids":["u1","u2"]}})
    with pytest.raises(RuntimeError, match="multiple broker order ids"):
        adapter.submit_order(req())
