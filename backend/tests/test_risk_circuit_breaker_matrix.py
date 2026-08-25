import pytest

from app.risk_circuit_breaker import CircuitBreakerConfig, TradingRiskCircuitBreaker


@pytest.mark.parametrize(
    "kwargs, expected_reason",
    [
        ({"daily_pnl": -1000, "drawdown": 0, "consecutive_losses": 0}, "max_daily_loss"),
        ({"daily_pnl": 0, "drawdown": 0.10, "consecutive_losses": 0}, "max_drawdown"),
        ({"daily_pnl": 0, "drawdown": 0, "consecutive_losses": 3}, "max_consecutive_losses"),
        ({"daily_pnl": 0, "drawdown": 0, "consecutive_losses": 0, "reconciliation_drift": True}, "reconciliation_drift"),
        ({"daily_pnl": 0, "drawdown": 0, "consecutive_losses": 0, "stale_data": True}, "stale_data"),
    ],
)
def test_each_critical_condition_blocks(kwargs, expected_reason):
    breaker = TradingRiskCircuitBreaker(
        CircuitBreakerConfig(
            max_daily_loss=1000,
            max_drawdown=0.10,
            max_consecutive_losses=3,
            block_on_reconciliation_drift=True,
            block_on_stale_data=True,
        )
    )
    status = breaker.evaluate(**kwargs)
    assert status.blocked is True
    assert expected_reason in status.reason
    assert breaker.can_trade() is False


def test_all_clear_allows_trading():
    breaker = TradingRiskCircuitBreaker(
        CircuitBreakerConfig(
            max_daily_loss=1000,
            max_drawdown=0.10,
            max_consecutive_losses=3,
        )
    )
    status = breaker.evaluate(
        daily_pnl=-100,
        drawdown=0.02,
        consecutive_losses=1,
        reconciliation_drift=False,
        stale_data=False,
    )
    assert status.blocked is False
    assert breaker.can_trade() is True


def test_breaker_latches_until_explicit_reset():
    breaker = TradingRiskCircuitBreaker(CircuitBreakerConfig(max_daily_loss=1000))
    assert breaker.evaluate(daily_pnl=-1000, drawdown=0, consecutive_losses=0).blocked
    assert breaker.evaluate(daily_pnl=0, drawdown=0, consecutive_losses=0).blocked
    breaker.reset()
    assert breaker.can_trade() is True
