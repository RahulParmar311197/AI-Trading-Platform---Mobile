import pytest

from app.broker_adapter import PaperBrokerAdapter
from app.broker_reconciliation_service import BrokerReconciliationService, ReconciliationConfig
from app.broker_router import BrokerRoute, BrokerRouter


def _service(unresolved=lambda: 0):
    broker = PaperBrokerAdapter()
    router = BrokerRouter([BrokerRoute(name="paper", adapter=broker, broker_account_id=7, generation="3")], "paper")
    return BrokerReconciliationService(
        router,
        ReconciliationConfig(route="paper", account_id="7", generation=3),
        unresolved_submission_intents=unresolved,
    )


def test_reconciliation_produces_verified_result_from_live_broker_state():
    result = _service().reconcile()
    assert result.verified is True
    assert result.account_id == "7"
    assert result.generation == 3
    assert result.open_orders_reconciled is True
    assert result.positions_reconciled is True
    assert result.submission_intents_resolved == 0


def test_reconciliation_rejects_unresolved_submission_intents():
    with pytest.raises(RuntimeError, match="submission intents"):
        _service(lambda: 1).reconcile()


def test_reconciliation_rejects_unready_broker():
    service = _service()
    service.router.get("paper").adapter.get_account = lambda: {"healthy": False, "authenticated": True}
    with pytest.raises(RuntimeError, match="not ready"):
        service.reconcile()


def test_reconciliation_rejects_account_mismatch():
    service = _service()
    service.config = ReconciliationConfig(route="paper", account_id="999", generation=3)
    with pytest.raises(RuntimeError, match="account"):
        service.reconcile()


def test_reconciliation_rejects_generation_mismatch():
    service = _service()
    service.config = ReconciliationConfig(route="paper", account_id="7", generation=99)
    with pytest.raises(RuntimeError, match="generation"):
        service.reconcile()
