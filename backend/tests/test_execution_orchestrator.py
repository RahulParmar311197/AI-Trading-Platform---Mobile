from datetime import timedelta

from app.execution_orchestrator import ExecutionOrchestrator
from app.order_intent import OrderIntent
from app.order_lifecycle import OrderLifecycle
from app.trade_plan import TradeAction, TradePlanValidator


def make_order(risk=50):
    return OrderIntent(
        symbol="NIFTY",
        side="BUY",
        entry=100.0,
        stop_loss=99.0,
        take_profit=102.0,
        quantity=10,
        risk_amount=risk,
        source="SMC",
        confidence=0.9,
    )


class FakeBroker:
    def __init__(self):
        self.calls = 0

    def submit(self, plan):
        self.calls += 1
        return "TEST-ORDER-1"


def make_plan(minutes=60):
    return TradePlanValidator().build(
        "NIFTY",
        TradeAction.BUY,
        100,
        95,
        110,
        10,
        100,
        minutes,
    )


def test_safe_signal_reaches_order_lifecycle():
    book = OrderLifecycle()

    result = ExecutionOrchestrator(
        lifecycle=book
    ).submit_signal(
        order=make_order(),
        equity=10000,
        daily_pnl=0,
        open_positions=0,
    )

    assert result.accepted
    assert len(book.orders) == 1


def test_risk_rejection_stops_execution():
    book = OrderLifecycle()

    result = ExecutionOrchestrator(
        lifecycle=book
    ).submit_signal(
        order=make_order(500),
        equity=10000,
        daily_pnl=0,
        open_positions=0,
    )

    assert not result.accepted
    assert result.reason == "RISK_REJECTED"
    assert len(book.orders) == 0


def test_live_and_kill_switch_are_required():
    broker = FakeBroker()

    orchestrator = ExecutionOrchestrator(
        broker=broker,
        live_enabled=False,
    )

    result = orchestrator.submit(
        make_plan(),
        kill_switch_armed=True,
    )

    assert not result.accepted
    assert result.reason == "LIVE_EXECUTION_DISABLED"
    assert broker.calls == 0

    orchestrator = ExecutionOrchestrator(
        broker=broker,
        live_enabled=True,
    )

    result = orchestrator.submit(
        make_plan(),
        kill_switch_armed=False,
    )

    assert not result.accepted
    assert result.reason == "KILL_SWITCH_BLOCKED"
    assert broker.calls == 0


def test_valid_plan_reaches_broker():
    broker = FakeBroker()

    result = ExecutionOrchestrator(
        broker=broker,
        live_enabled=True,
    ).submit(
        make_plan(),
        kill_switch_armed=True,
    )

    assert result.accepted
    assert result.order_id == "TEST-ORDER-1"
    assert broker.calls == 1


def test_expired_plan_is_blocked():
    broker = FakeBroker()

    result = ExecutionOrchestrator(
        broker=broker,
        live_enabled=True,
    ).submit(
        make_plan(-1),
        kill_switch_armed=True,
    )

    assert not result.accepted
    assert result.reason == "TRADE_PLAN_EXPIRED"
    assert broker.calls == 0