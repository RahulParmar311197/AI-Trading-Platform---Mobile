from app.ai_decision_engine import TradingDecision
from app.operational_metrics import TradingMetricsCollector
from app.pretrade_orchestrator import PreTradeOrchestrator
from app.risk_circuit_breaker import CircuitBreakerConfig, TradingRiskCircuitBreaker
from app.risk_circuit_observability import ObservableRiskCircuitBreaker
from app.trading_observability import TradingAuditLogger


def test_blocked_circuit_breaker_prevents_order_authorization():
    metrics = TradingMetricsCollector()
    audit = TradingAuditLogger()
    breaker = ObservableRiskCircuitBreaker(
        TradingRiskCircuitBreaker(CircuitBreakerConfig(max_daily_loss=1000)),
        metrics=metrics,
        audit=audit,
    )
    breaker.engage("test safety halt")

    orchestrator = PreTradeOrchestrator(circuit_breaker=breaker, metrics=metrics, audit=audit)
    decision = TradingDecision(decision="BUY", confidence=0.95, rationale="integration test")

    result = orchestrator.authorize_decision(
        symbol="NIFTY",
        decision=decision,
        equity=100000,
        daily_pnl=0,
        open_positions=0,
    )

    assert result.approved is False
    assert result.gateway is None
    assert "circuit breaker" in result.reason
    assert metrics.snapshot()["circuit_breaker_blocks"] >= 1
