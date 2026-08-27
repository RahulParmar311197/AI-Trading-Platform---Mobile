import pytest

from app.ai_execution_orchestrator import AIExecutionResult
from app.confluence_execution_orchestrator import ConfluenceExecutionOrchestrator
from app.signal_confluence import SignalDecision


class FakeAIOrchestrator:
    def __init__(self):
        self.calls = 0

    async def evaluate_and_execute(self, *args, **kwargs):
        self.calls += 1
        return AIExecutionResult(decision=None, order_request=object(), execution=object())


@pytest.mark.asyncio
async def test_hold_confluence_never_calls_ai_executor():
    fake = FakeAIOrchestrator()
    orchestrator = ConfluenceExecutionOrchestrator(ai_orchestrator=fake)
    result = await orchestrator.evaluate_and_execute(
        object(),
        ict={"direction": "neutral"},
        technical={"direction": "neutral"},
        equity=100000,
        client_order_id="hold-1",
    )
    assert result.signal.action == "HOLD"
    assert result.execution is None
    assert fake.calls == 0


@pytest.mark.asyncio
async def test_actionable_confluence_delegates_to_canonical_ai_executor():
    fake = FakeAIOrchestrator()
    orchestrator = ConfluenceExecutionOrchestrator(ai_orchestrator=fake)
    result = await orchestrator.evaluate_and_execute(
        object(),
        ict={"direction": "bullish"},
        technical={"direction": "bullish"},
        equity=100000,
        client_order_id="buy-1",
    )
    assert result.signal.action == "BUY"
    assert result.execution is not None
    assert fake.calls == 1
