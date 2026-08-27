from datetime import datetime

import pytest

from app.broker_adapter import PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter
from app.broker_snapshot import BrokerSnapshot


class CountingPaperBroker(PaperBrokerAdapter):
    def __init__(self):
        super().__init__()
        self.order_snapshot_calls = 0
        self.position_snapshot_calls = 0

    def get_order_snapshot(self):
        self.order_snapshot_calls += 1
        return super().get_order_snapshot()

    def get_position_snapshot(self):
        self.position_snapshot_calls += 1
        return super().get_position_snapshot()


def test_router_authoritative_reconciliation_uses_coordinator(tmp_path):
    broker = CountingPaperBroker()
    router = BrokerRouter(
        [BrokerRoute("paper", broker, broker_account_id=7, generation="g1")],
        "paper",
    )

    result = router.reconcile_authoritative([], [], "paper")

    assert result.verified is True
    assert result.context.account_id == "7"
    assert result.context.broker_route == "paper"
    assert result.context.route_generation == "g1"
    assert result.context.snapshot_fingerprint
    assert broker.order_snapshot_calls == 1
    assert broker.position_snapshot_calls == 1


def test_router_authoritative_reconciliation_requires_account_binding():
    router = BrokerRouter([BrokerRoute("paper", PaperBrokerAdapter())], "paper")

    with pytest.raises(RuntimeError, match="broker account"):
        router.reconcile_authoritative([], [], "paper")


def test_router_authoritative_reconciliation_requires_route_generation():
    router = BrokerRouter(
        [BrokerRoute("paper", PaperBrokerAdapter(), broker_account_id=7)],
        "paper",
    )

    with pytest.raises(RuntimeError, match="route generation"):
        router.reconcile_authoritative([], [], "paper")


def test_router_authoritative_reconciliation_rejects_snapshot_context_mismatch():
    broker = PaperBrokerAdapter()
    router = BrokerRouter(
        [BrokerRoute("paper", broker, broker_account_id=7, generation="g1")],
        "paper",
    )

    snapshot = BrokerSnapshot(
        orders=[],
        positions=[],
        broker_route="other",
        broker_account_id=7,
    )
    coordinator = router.reconciliation_engine
    assert coordinator is router.reconciliation_engine
    with pytest.raises(ValueError, match="route"):
        from app.reconciliation_coordinator import ReconciliationCoordinator

        ReconciliationCoordinator(
            engine=coordinator,
            route="paper",
            account_id="7",
            route_generation="g1",
        ).reconcile(
            internal_orders=[],
            internal_positions=[],
            broker_snapshot=snapshot,
        )
