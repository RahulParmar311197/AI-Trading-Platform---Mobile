from app.ai_market_analyst import AIMarketAnalyst
from app.market_data import Candle


def candles():
    return [Candle(timestamp=i, open=100+i*.1, high=101+i*.1, low=99+i*.1, close=100.5+i*.1, volume=1000) for i in range(50)]


def test_local_analysis_is_grounded_in_signal_engine():
    result = AIMarketAnalyst().analyze(candles())
    assert result.bias in {"BULLISH", "BEARISH", "NEUTRAL"}
    assert result.grounded_snapshot["candle_count"] == 50
    assert result.evidence


def test_empty_data_does_not_fabricate_market_facts():
    result = AIMarketAnalyst().analyze([])
    assert result.bias == "NEUTRAL"
    assert "NO_MARKET_DATA" in result.evidence
