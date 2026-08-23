from app.execution_orchestrator import ExecutionOrchestrator
from app.paper_broker_adapter import PaperBrokerAdapter
from app.paper_execution import PaperBroker
from app.trade_plan import TradeAction, TradePlanValidator


def make_plan(risk=100):
    return TradePlanValidator().build("NIFTY", TradeAction.BUY, 100, 95, 110, 10, risk)


def test_valid_plan_reaches_paper_broker():
    broker = PaperBroker()
    adapter = PaperBrokerAdapter(broker, equity=100_000)
    result = ExecutionOrchestrator(broker=adapter, live_enabled=True).submit(make_plan(), kill_switch_armed=True)
    assert result.accepted
    assert result.order_id is not None
    assert len(broker.open_positions()) == 1


def test_risk_veto_stops_paper_broker():
    broker = PaperBroker()
    adapter = PaperBrokerAdapter(broker, equity=10_000)
    result = ExecutionOrchestrator(broker=adapter, live_enabled=True).submit(make_plan(500), kill_switch_armed=True)
    assert not result.accepted
    assert result.reason.startswith("BROKER_REJECTED: RISK_VETO:")
    assert broker.open_positions() == []


def test_kill_switch_prevents_paper_submission():
    broker = PaperBroker()
    adapter = PaperBrokerAdapter(broker, equity=100_000)
    result = ExecutionOrchestrator(broker=adapter, live_enabled=True).submit(make_plan(), kill_switch_armed=False)
    assert not result.accepted
    assert result.reason == "KILL_SWITCH_BLOCKED"
    assert broker.open_positions() == []
