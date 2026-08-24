from app.broker_adapter import BrokerOrderRequest
from app.decision_execution_guard import execute_decision
from app.ensemble import EnsembleDecision

class FakeExecution:
    def __init__(self):
        self.requests = []
    def submit(self, request):
        self.requests.append(request)
        return type("Result", (), {"status": "FILLED", "order_id": request.client_order_id})()

def decision(action):
    return EnsembleDecision(action, 0.8 if action == "BUY" else -0.8, 0.8, 0.9 if action == "BUY" else 0.1, 4.0 if action == "BUY" else -4.0, "NORMAL", [])

def request_factory(side):
    return BrokerOrderRequest(client_order_id="guard-1", symbol="NIFTY", side=side, quantity=1)

def test_no_trade_never_reaches_execution():
    execution = FakeExecution()
    result = execute_decision(decision("NO_TRADE"), execution, request_factory)
    assert result.executed is False
    assert result.result is None
    assert result.reason == "NO_TRADE"
    assert execution.requests == []

def test_buy_reaches_execution_service_only_after_side_validation():
    execution = FakeExecution()
    result = execute_decision(decision("BUY"), execution, request_factory)
    assert result.executed is True
    assert len(execution.requests) == 1
    assert execution.requests[0].side == "BUY"

def test_side_mismatch_is_blocked():
    execution = FakeExecution()
    result = execute_decision(decision("SELL"), execution, lambda _: request_factory("BUY"))
    assert result.executed is False
    assert result.reason == "DECISION_SIDE_MISMATCH"
    assert execution.requests == []
