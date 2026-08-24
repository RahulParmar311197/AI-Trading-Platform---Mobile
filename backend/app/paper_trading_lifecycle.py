from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from app.ai_decision_engine import AIDecisionEngine
from app.market_context import Candle
from app.paper_trading import PaperBroker
from app.pretrade_orchestrator import PreTradeOrchestrator
from app.trade_plan import TradePlan


@dataclass(frozen=True)
class LifecycleEvent:
    timestamp: datetime
    event: str
    order_id: str | None
    message: str


class PaperTradingLifecycle:
    """Coordinates signal -> authorization -> paper order -> reconciliation."""

    def __init__(self, broker: PaperBroker | None = None, decision_engine: AIDecisionEngine | None = None, orchestrator: PreTradeOrchestrator | None = None):
        self.broker = broker or PaperBroker()
        self.decision_engine = decision_engine or AIDecisionEngine()
        self.orchestrator = orchestrator or PreTradeOrchestrator()
        self.events: list[LifecycleEvent] = []

    def _event(self, event: str, message: str, order_id: str | None = None) -> None:
        self.events.append(LifecycleEvent(datetime.now(timezone.utc), event, order_id, message))

    def process(self, symbol: str, timeframe: str, candles: Sequence[Candle], equity: float) -> str | None:
        try:
            context = self.orchestrator.pipeline.build(symbol, timeframe, candles)
            decision = self.decision_engine.decide(context)
            if decision.decision == "HOLD":
                self._event("SIGNAL_HOLD", "decision engine returned HOLD")
                return None
            plan = self.orchestrator.build_plan(context, decision, equity)
            if plan is None:
                self._event("RISK_REJECT", "pre-trade authorization rejected proposal")
                return None
            order_id = self.broker.submit(plan)
            self._event("ORDER_SUBMITTED", "paper order submitted", order_id)
            return order_id
        except Exception as exc:
            self._event("ERROR", str(exc))
            raise

    def reconcile(self) -> list[str]:
        errors = self.broker.reconcile()
        self._event("RECONCILIATION", "clean" if not errors else f"{len(errors)} error(s)")
        return errors

    def snapshot(self) -> dict:
        return {"broker": self.broker.snapshot(), "events": [e.__dict__ for e in self.events]}
