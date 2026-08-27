from datetime import datetime, timedelta, timezone

import pytest

from app.ai_decision_engine import AIDecisionEngine
from app.market_context_builder import MarketContextBuilder
from app.paper_candle_provider import PaperCandleProvider


def make_candles(n=120):
    start = datetime.now(timezone.utc) - timedelta(minutes=n)
    result = []
    price = 100.0
    for i in range(n):
        price += 0.15
        result.append({
            "timestamp": start + timedelta(minutes=i),
            "open": price - 0.10,
            "high": price + 0.20,
            "low": price - 0.20,
            "close": price,
            "volume": 1000 + i,
        })
    return result


@pytest.mark.asyncio
async def test_paper_candles_reach_market_context_and_ai():
    provider = PaperCandleProvider(make_candles())
    candles = await provider.latest("NIFTY", interval="1m", limit=120)
    context = MarketContextBuilder().build("NIFTY", candles)
    assert context.symbol == "NIFTY"
    assert context.data_quality in {"GOOD", "DEGRADED"}
    assert context.indicators.values["ema_20"] is not None
    decision = AIDecisionEngine().decide(context)
    assert decision.symbol == "NIFTY"
    assert decision.decision in {"BUY", "SELL", "HOLD"}
    assert 0.0 <= decision.confidence <= 1.0
