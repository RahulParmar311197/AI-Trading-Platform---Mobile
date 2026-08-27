from datetime import datetime, timedelta, timezone

from app.ai_backtest_strategy import CanonicalAIBacktestStrategy
from app.ai_decision_engine import AIDecisionEngine
from app.market_context import Candle, IndicatorSnapshot, StructureSnapshot, SMCSnapshot, ICTSnapshot, MarketContext


class FakeBuilder:
    def __init__(self):
        self.calls = []

    def build(self, symbol, timeframe, candles, *, as_of):
        self.calls.append((symbol, timeframe, tuple(candles), as_of))
        return MarketContext(
            symbol=symbol,
            timeframe=timeframe,
            as_of=as_of,
            candles=tuple(candles),
            indicators=IndicatorSnapshot({
                "ema_20": 101.0, "ema_50": 100.0, "rsi_14": 60.0,
                "macd_histogram": 1.0, "atr_14": 1.0, "adx_14": 30.0,
            }),
            structure=StructureSnapshot("BULLISH", "BULLISH", None, None),
            smc=SMCSnapshot("DISCOUNT", None, (), ()),
            ict=ICTSnapshot(None, False, None, ()),
            regime="TRENDING_BULLISH",
            data_quality="GOOD",
        )


def test_strategy_passes_only_visible_bars_to_builder():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = tuple(Candle(start + timedelta(minutes=i), 100+i, 101+i, 99+i, 100+i, 1000) for i in range(55))
    builder = FakeBuilder()
    strategy = CanonicalAIBacktestStrategy(context_builder=builder, decision_engine=AIDecisionEngine(), symbol="NIFTY", timeframe="1m")
    signal = strategy.signal(50, candles)
    assert signal == ("BUY", 1)
    assert len(builder.calls) == 1
    assert len(builder.calls[0][2]) == 51
    assert builder.calls[0][2][-1].timestamp == candles[50].timestamp
