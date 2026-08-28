from __future__ import annotations

from app.operational_metrics import TradingMetricsCollector
from app.risk_circuit_breaker import CircuitBreakerStatus, TradingRiskCircuitBreaker
from app.safety_state import SafetyStateStore
from app.trading_observability import TradingAuditLogger


class ObservableRiskCircuitBreaker:
    """Durable, observable fail-closed risk circuit breaker."""

    def __init__(self, breaker: TradingRiskCircuitBreaker | None = None,
                 metrics: TradingMetricsCollector | None = None,
                 audit: TradingAuditLogger | None = None,
                 safety_store: SafetyStateStore | None = None):
        self.breaker = breaker or TradingRiskCircuitBreaker()
        self.metrics = metrics or TradingMetricsCollector()
        self.audit = audit or TradingAuditLogger()
        self.safety_store = safety_store
        if self.safety_store is not None:
            blocked, reason = self.safety_store.risk_circuit_status()
            if blocked:
                self.breaker.engage(reason or "persisted risk circuit")

    def evaluate(self, **kwargs) -> CircuitBreakerStatus:
        status = self.breaker.evaluate(**kwargs)
        if status.blocked:
            self._persist_engagement(status.reason)
            self.metrics.increment("circuit_breaker_blocks")
            self.audit.emit("CIRCUIT_BREAKER_BLOCK", severity="WARNING", data={"reason": status.reason})
        return status

    def engage(self, reason: str) -> None:
        self.breaker.engage(reason)
        self._persist_engagement(reason)
        self.metrics.increment("circuit_breaker_blocks")
        self.audit.emit("CIRCUIT_BREAKER_ENGAGED", severity="CRITICAL", data={"reason": reason})

    def _persist_engagement(self, reason: str) -> None:
        if self.safety_store is not None:
            self.safety_store.engage_risk_circuit(reason)

    def can_trade(self) -> bool:
        return self.breaker.can_trade()

    def reset(self) -> None:
        if self.safety_store is not None:
            self.safety_store.reset_risk_circuit()
        self.breaker.reset()
        self.audit.emit("CIRCUIT_BREAKER_RESET", severity="WARNING")

    def status(self) -> CircuitBreakerStatus:
        return self.breaker.status()
