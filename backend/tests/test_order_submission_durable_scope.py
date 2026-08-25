import pytest

from app.order_submission_service import BrokerSubmissionResult, OrderIntent, OrderSubmissionService
from app.transactional_execution_repository import TransactionalExecutionRepository


class Broker:
    def __init__(self):
        self.calls = 0

    def submit(self, intent):
        self.calls += 1
        return BrokerSubmissionResult("broker-1", intent.client_order_id)


def test_submission_requires_exact_durable_order_scope(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    broker = Broker()
    service = OrderSubmissionService(repo, broker)
    bad = OrderIntent(order, "NIFTY", "SELL", 5, 1, "primary", "idem-1")
    with pytest.raises(ValueError, match="does not match durable order scope"):
        service.submit(bad)
    assert broker.calls == 0
    repo.close()


def test_submission_registers_pending_before_broker_call(tmp_path):
    repo = TransactionalExecutionRepository(str(tmp_path / "execution.db"))
    order = repo.create_order("NIFTY", "BUY", 5, broker_account_id=1, broker_route="primary")
    broker = Broker()
    service = OrderSubmissionService(repo, broker)
    result = service.submit(OrderIntent(order, "NIFTY", "BUY", 5, 1, "primary", "idem-1"))
    assert result.broker_order_id == "broker-1"
    assert repo.get_submission("idem-1").status == "SUBMITTED"
    assert broker.calls == 1
    repo.close()
