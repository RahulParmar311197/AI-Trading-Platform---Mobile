from __future__ import annotations

from app.operational_metrics import TradingMetricsCollector
from app.risk_circuit_breaker import CircuitBreakerStatus, TradingRiskCircuitBreaker
from app.trading_observability import TradingAuditLogger


class ObservableRiskCircuitBreaker:
    """Wraps the safety breaker so blocks are measurable and auditable."""

    def __init__(self, breaker: TradingRiskCircuitBreaker | None = None,
                 metrics: TradingMetricsCollector | None = None,
                 audit: TradingAuditLogger | None = None):
        self.breaker = breaker or TradingRiskCircuitBreaker()
        self.metrics = metrics or TradingMetricsCollector()
        self.audit = audit or TradingAuditLogger()

    def evaluate(self, **kwargs) -> CircuitBreakerStatus:
        status = self.breaker.evaluate(**kwargs)
        if status.blocked:
            self.metrics.increment("circuit_breaker_blocks")
            self.audit.emit("CIRCUIT_BREAKER_BLOCK", severity="WARNING", data={"reason": status.reason})
        return status

    def engage(self, reason: str) -> None:
        self.breaker.engage(reason)
        self.metrics.increment("circuit_breaker_blocks")
        self.audit.emit("CIRCUIT_BREAKER_ENGAGED", severity="CRITICAL", data={"reason": reason})

    def can_trade(self) -> bool:
        return self.breaker.can_trade()

    def reset(self) -> None:
        self.breaker.reset()
        self.audit.emit("CIRCUIT_BREAKER_RESET", severity="WARNING")

    def status(self) -> CircuitBreakerStatus:
        return self.breaker.status()
