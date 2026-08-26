import pytest

from app.broker_adapter import PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter
from app.broker_position_snapshot import BrokerPositionSnapshot


class IncompletePositionPaper(PaperBrokerAdapter):
    def get_position_snapshot(self):
        return BrokerPositionSnapshot(positions=self.get_positions(), complete=False, source="test")


def test_router_requires_authoritative_positions_for_reconciliation():
    adapter = IncompletePositionPaper()
    router = BrokerRouter([BrokerRoute(name="paper", adapter=adapter)], "paper")
    with pytest.raises(RuntimeError, match="position snapshot is not authoritative"):
        router.get_snapshot()
