from app.order_intent import OrderIntent
from app.risk_gateway import authorize
from app.risk_engine import RiskLimits


def order(risk=50.0, qty=1.0):
    return OrderIntent('NIFTY', 'BUY', 100.0, 90.0, 120.0, qty, risk, 'strategy', 0.9)


def test_safe_order_is_authorized():
    result = authorize(order=order(), equity=10000, daily_pnl=0, open_positions=0)
    assert result.approved


def test_excessive_trade_risk_is_rejected():
    result = authorize(
        order=order(risk=200),
        equity=10000,
        daily_pnl=0,
        open_positions=0,
        limits=RiskLimits(max_risk_percent=1.0),
    )
    assert not result.approved
    assert 'trade risk exceeds limit' in result.decision.reasons


def test_daily_loss_blocks_order():
    result = authorize(order=order(), equity=10000, daily_pnl=-400, open_positions=0)
    assert not result.approved
