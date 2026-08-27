import pytest

from app.ai_decision_engine import TradingDecision
from app.ai_execution_orchestrator import AIExecutionOrchestrator
from app.instruments import InstrumentProvider, InstrumentSpec


class FakeDecisionEngine:
    def __init__(self, decision):
        self.decision = decision

    def decide(self, context, *, prediction=None, ml_confidence=0.0):
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


@pytest.mark.asyncio
async def test_buy_reaches_submitter_exactly_once():
    submitter = FakeSubmitter()
    orchestrator = AIExecutionOrchestrator(
        decision_engine=FakeDecisionEngine(make_decision()),
        instrument_provider=FakeProvider(), order_submitter=submitter,
    )
    result = await orchestrator.evaluate_and_execute(
        object(), equity=100_000, client_order_id="ai-test-1"
    )
    assert result.order_request is not None
    assert result.execution == {"status": "accepted"}
    assert len(submitter.requests) == 1
    assert submitter.requests[0].quantity == 100


@pytest.mark.asyncio
async def test_hold_never_reaches_submitter():
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
    assert submitter.requests == []
