from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.decision_cycle_service import DecisionCycleService
from app.market_data import Candle


class StubAnalysisPipeline:
    def __init__(self, context):
        self.context = context
        self.calls = []

    def build(self, symbol, timeframe, candles):
        self.calls.append((symbol, timeframe, candles))
        return self.context


class StubDecisionEngine:
    def __init__(self, decision):
        self.decision = decision
        self.calls = []

    def decide(self, context):
        self.calls.append(context)
        return self.decision


def candle(symbol="NIFTY", timestamp=None):
    return Candle(
        symbol=symbol,
        timestamp=timestamp or datetime.now(timezone.utc),
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=1000.0,
    )


def test_evaluate_composes_analysis_and_decision_layers():
    context = object()
    decision = object()
    analysis = StubAnalysisPipeline(context)
    engine = StubDecisionEngine(decision)
    service = DecisionCycleService(analysis_pipeline=analysis, decision_engine=engine)

    candles = [candle()]
    result = service.evaluate("NIFTY", "5m", candles)

    assert result.context is context
    assert result.decision is decision
    assert analysis.calls == [("NIFTY", "5m", candles)]
    assert engine.calls == [context]


def test_evaluate_propagates_analysis_validation_errors():
    class FailingAnalysis:
        def build(self, symbol, timeframe, candles):
            raise ValueError("invalid market data")

    service = DecisionCycleService(
        analysis_pipeline=FailingAnalysis(),
        decision_engine=StubDecisionEngine(object()),
    )

    with pytest.raises(ValueError, match="invalid market data"):
        service.evaluate("NIFTY", "5m", [candle()])


def test_evaluate_does_not_call_decision_engine_when_analysis_fails():
    class FailingAnalysis:
        def build(self, symbol, timeframe, candles):
            raise RuntimeError("analysis failed")

    engine = StubDecisionEngine(object())
    service = DecisionCycleService(
        analysis_pipeline=FailingAnalysis(), decision_engine=engine
    )

    with pytest.raises(RuntimeError, match="analysis failed"):
        service.evaluate("NIFTY", "5m", [candle()])

    assert engine.calls == []
