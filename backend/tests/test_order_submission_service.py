import pytest

from app.order_submission_service import BrokerSubmissionResult, OrderIntent, OrderSubmissionService


class FakeBroker:
    def __init__(self):
        self.calls = 0

    def submit(self, intent):
        self.calls += 1
        return BrokerSubmissionResult(f"broker-{self.calls}", intent.client_order_id)


def intent(key="order-1"):
    return OrderIntent("client-1", "NIFTY", "BUY", 5, 1, "primary", key)


def test_safe_order_reaches_broker_once():
    broker = FakeBroker()
    service = OrderSubmissionService(broker)
    first = service.submit(intent())
    second = service.submit(intent())
    assert first == second
    assert broker.calls == 1


@pytest.mark.parametrize("kwargs", [
    {"emergency_halt": True},
    {"reconciliation_ready": False},
    {"broker_healthy": False},
    {"risk_allowed": False},
])
def test_safety_failure_prevents_broker_submission(kwargs):
    broker = FakeBroker()
    service = OrderSubmissionService(broker)
    with pytest.raises(PermissionError):
        service.submit(intent(), **kwargs)
    assert broker.calls == 0


def test_missing_idempotency_key_is_rejected():
    broker = FakeBroker()
    service = OrderSubmissionService(broker)
    with pytest.raises(ValueError, match="idempotency key"):
        service.submit(intent(""))
