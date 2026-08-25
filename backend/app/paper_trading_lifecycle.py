from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from typing import Sequence

from app.ai_decision_engine import AIDecisionEngine
from app.market_context import Candle
from app.operational_metrics import TradingMetricsCollector
from app.paper_trading import PaperBroker
from app.pretrade_orchestrator import PreTradeOrchestrator
from app.trading_observability import TradingAuditLogger


@dataclass(frozen=True)
class LifecycleEvent:
    timestamp: datetime
    event: str
    order_id: str | None
    message: str


class PaperTradingLifecycle:
    """Coordinates signal -> authorization -> paper order -> reconciliation and telemetry."""

    def __init__(self, broker: PaperBroker | None = None, decision_engine: AIDecisionEngine | None = None,
                 orchestrator: PreTradeOrchestrator | None = None, metrics: TradingMetricsCollector | None = None,
                 audit: TradingAuditLogger | None = None):
        self.broker = broker or PaperBroker()
        self.decision_engine = decision_engine or AIDecisionEngine()
        self.orchestrator = orchestrator or PreTradeOrchestrator()
        self.metrics = metrics or TradingMetricsCollector()
        self.audit = audit or TradingAuditLogger()
        self.events: list[LifecycleEvent] = []

    def _event(self, event: str, message: str, order_id: str | None = None, symbol: str | None = None) -> None:
        self.events.append(LifecycleEvent(datetime.now(timezone.utc), event, order_id, message))
        self.audit.emit(event, symbol=symbol, client_order_id=order_id, data={"message": message})

    def process(self, symbol: str, timeframe: str, candles: Sequence[Candle], equity: float) -> str | None:
        started = monotonic()
        self.metrics.increment("signals")
        self.audit.emit("SIGNAL_GENERATED", symbol=symbol, data={"timeframe": timeframe})
        try:
            context = self.orchestrator.pipeline.build(symbol, timeframe, candles)
            decision = self.decision_engine.decide(context)
            self.audit.emit("AI_DECISION", symbol=symbol, data={"decision": decision.decision})
            if decision.decision == "HOLD":
                self._event("SIGNAL_HOLD", "decision engine returned HOLD", symbol=symbol)
                return None
            plan = self.orchestrator.build_plan(context, decision, equity)
            if plan is None:
                self.audit.emit("RISK_REJECTED", symbol=symbol)
                self._event("RISK_REJECT", "pre-trade authorization rejected proposal", symbol=symbol)
                self.metrics.increment("orders_rejected")
                return None
            order_id = self.broker.submit(plan)
            elapsed_ms = (monotonic() - started) * 1000.0
            self.metrics.increment("orders_submitted")
            self.metrics.record_latency(elapsed_ms)
            self._event("ORDER_SUBMITTED", "paper order submitted", order_id, symbol)
            return order_id
        except Exception as exc:
            self.audit.emit("ERROR", symbol=symbol, severity="ERROR", data={"message": str(exc)})
            self._event("ERROR", str(exc), symbol=symbol)
            raise

    def reconcile(self) -> list[str]:
        errors = self.broker.reconcile()
        if errors:
            self.metrics.increment("reconciliation_failures", len(errors))
        self._event("RECONCILIATION", "clean" if not errors else f"{len(errors)} error(s)")
        return errors

    def snapshot(self) -> dict:
        return {"broker": self.broker.snapshot(), "events": [e.__dict__ for e in self.events], "metrics": self.metrics.snapshot()}
