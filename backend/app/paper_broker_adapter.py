from __future__ import annotations

from app.execution_orchestrator import BrokerAdapter
from app.paper_execution import PaperBroker, paper_broker
from app.trade_plan import TradePlan


class PaperBrokerAdapter(BrokerAdapter):
    """Translate validated TradePlans into risk-checked paper positions."""

    def __init__(self, broker: PaperBroker | None = None, equity: float = 100_000.0):
        if equity <= 0:
            raise ValueError("equity must be positive")
        self.broker = broker or paper_broker
        self.equity = equity

    def submit(self, plan: TradePlan) -> str:
        position = self.broker.open(
            symbol=plan.symbol,
            side=plan.action.value,
            quantity=plan.quantity,
            entry=plan.entry,
            stop_loss=plan.stop_loss,
            target=plan.take_profit,
            equity=self.equity,
        )
        return position.id
