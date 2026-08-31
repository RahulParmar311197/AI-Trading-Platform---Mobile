from app.broker_adapter import BrokerOrderRequest
from app.durable_risk_reservations import DurableExposureReservationAdapter
from app.risk_gate import PreTradeRiskGate, RiskLimits, RiskSnapshot


class FakeStore:
    def __init__(self):
        self.calls = []

    def reserve(self, **kwargs):
        self.calls.append(("reserve", kwargs))
        return "reservation-1"

    def reconcile_client_order(self, **kwargs):
        self.calls.append(("reconcile", kwargs))
        return "RELEASED" if kwargs["broker_status"] != "PARTIALLY_FILLED" else "ACTIVE"


def request():
    return BrokerOrderRequest(
        client_order_id="manual-1",
        symbol="NIFTY",
        side="BUY",
        quantity=5,
        broker_account_id=7,
        broker_route="upstox:account:7",
    )


def test_durable_adapter_uses_bound_broker_scope():
    store = FakeStore()
    adapter = DurableExposureReservationAdapter(store, 20)
    adapter.bind_request(request())
    assert adapter.reserve("manual-1", 5, 0, 20)
    kind, call = store.calls[0]
    assert kind == "reserve"
    assert call["broker_account_id"] == "7"
    assert call["broker_route"] == "upstox:account:7"
    assert call["amount"] == 5


def test_pretrade_gate_can_use_durable_adapter():
    store = FakeStore()
    adapter = DurableExposureReservationAdapter(store, 20)
    gate = PreTradeRiskGate(
        RiskLimits(10, 20, 1000, 200),
        reservations=adapter,
    )
    req = request()
    adapter.bind_request(req)
    result = gate.reserve(req, RiskSnapshot(position_quantity=0, broker_ready=True))
    assert result.allowed
    assert store.calls[0][0] == "reserve"


def test_terminal_release_and_partial_fill_are_durable_operations():
    store = FakeStore()
    adapter = DurableExposureReservationAdapter(store, 20)
    adapter.bind_request(request())
    adapter.update("manual-1", 2, 5, 20)
    adapter.release("manual-1")
    assert store.calls[0][1]["broker_status"] == "PARTIALLY_FILLED"
    assert store.calls[1][1]["broker_status"] == "CANCELLED"
