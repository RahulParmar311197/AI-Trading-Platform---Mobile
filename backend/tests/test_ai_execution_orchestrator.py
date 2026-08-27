import pytest

from app.ai_decision_engine import TradingDecision
from app.ai_execution_orchestrator import AIRiskSnapshot, AIExecutionOrchestrator
from app.instruments import InstrumentProvider, InstrumentSpec


class FakeDecisionEngine:
    def __init__(self, decision):
        self.decision = decision

    def decide(self, context, *, prediction=None, ml_confidence=0.0, confluence=None):
        return self.decision


class FakeProvider(InstrumentProvider):
    def resolve(self, symbol):
        if symbol != "NIFTY":
            return None
        return InstrumentSpec(
            symbol="NIFTY", security_id="NIFTY-TEST", exchange_segment="NSE_FO",
            lot_size=50, tick_size=0.05, multiplier=1.0, tradable=True,
        )


class FakeSubmitter:
    def __init__(self):
        self.requests = []

    async def submit(self, request):
        self.requests.append(request)
        return {"status": "accepted"}


def make_decision(side="BUY"):
    return TradingDecision(
        symbol="NIFTY", decision=side, confidence=0.9,
        entry=100.0, stop_loss=90.0 if side == "BUY" else 110.0,
        target=120.0 if side == "BUY" else 80.0, reasons=("test",),
    )


def risk_snapshot(**overrides):
    values = dict(daily_pnl=0.0, open_positions=0, recent_losses=0)
    values.update(overrides)
    return AIRiskSnapshot(**values)


@pytest.mark.asyncio
async def test_buy_reaches_submitter_exactly_once_after_risk_approval():
    submitter = FakeSubmitter()
    orchestrator = AIExecutionOrchestrator(
        decision_engine=FakeDecisionEngine(make_decision()),
        instrument_provider=FakeProvider(), order_submitter=submitter,
    )
    result = await orchestrator.evaluate_and_execute(
        object(), equity=100_000, client_order_id="ai-test-1",
        risk_snapshot=risk_snapshot(),
    )
    assert result.order_request is not None
    assert result.execution == {"status": "accepted"}
    assert result.risk_decision is not None and result.risk_decision.allowed
    assert len(submitter.requests) == 1
    assert submitter.requests[0].quantity == 100


@pytest.mark.asyncio
async def test_risk_rejection_never_reaches_submitter():
    submitter = FakeSubmitter()
    orchestrator = AIExecutionOrchestrator(
        decision_engine=FakeDecisionEngine(make_decision()),
        instrument_provider=FakeProvider(), order_submitter=submitter,
    )
    result = await orchestrator.evaluate_and_execute(
        object(), equity=100_000, client_order_id="ai-test-risk-veto",
        risk_snapshot=risk_snapshot(daily_pnl=-3_000),
    )
    assert result.execution is None
    assert result.risk_decision is not None and not result.risk_decision.allowed
    assert submitter.requests == []


@pytest.mark.asyncio
async def test_trade_requires_authoritative_risk_snapshot():
    submitter = FakeSubmitter()
    orchestrator = AIExecutionOrchestrator(
        decision_engine=FakeDecisionEngine(make_decision()),
        instrument_provider=FakeProvider(), order_submitter=submitter,
    )
    with pytest.raises(RuntimeError, match="risk snapshot"):
        await orchestrator.evaluate_and_execute(
            object(), equity=100_000, client_order_id="ai-test-missing-risk"
        )
    assert submitter.requests == []


@pytest.mark.asyncio
async def test_hold_never_reaches_submitter_or_requires_risk_snapshot():
    submitter = FakeSubmitter()
    orchestrator = AIExecutionOrchestrator(
        decision_engine=FakeDecisionEngine(
            TradingDecision(symbol="NIFTY", decision="HOLD", confidence=0.9,
                            entry=None, stop_loss=None, target=None, reasons=("hold",))
        ),
        instrument_provider=FakeProvider(), order_submitter=submitter,
    )
    result = await orchestrator.evaluate_and_execute(
        object(), equity=100_000, client_order_id="ai-test-2"
    )
    assert result.order_request is None
    assert result.execution is None
    assert result.risk_decision is None
    assert submitter.requests == []
