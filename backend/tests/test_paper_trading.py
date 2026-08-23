from datetime import datetime, timedelta, timezone

import pytest

from app.paper_trading import PaperBroker
from app.trade_plan import TradeAction, TradePlanValidator


def make_plan(minutes=60):
    return TradePlanValidator().build("NIFTY", TradeAction.BUY, 100, 95, 110, 10, 100, minutes)


def test_paper_broker_fills_and_tracks_order():
    broker = PaperBroker(100000)
    order_id = broker.submit(make_plan())
    assert order_id == "PAPER-000001"
    assert broker.orders[order_id].status == "FILLED"
    assert broker.orders[order_id].symbol == "NIFTY"


def test_paper_broker_cancel_is_idempotently_safe():
    broker = PaperBroker()
    order_id = broker.submit(make_plan())
    assert broker.cancel(order_id)
    assert broker.orders[order_id].status == "CANCELLED"
    assert not broker.cancel(order_id)


def test_expired_plan_is_rejected():
    broker = PaperBroker()
    plan = make_plan()
    expired = plan.__class__(plan.symbol, plan.action, plan.entry, plan.stop_loss, plan.take_profit, plan.quantity, plan.risk_amount, plan.reward_amount, plan.risk_reward, datetime.now(timezone.utc) - timedelta(seconds=1))
    with pytest.raises(ValueError, match="expired"):
        broker.submit(expired)
