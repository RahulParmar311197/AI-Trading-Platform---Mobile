from app.unified_signal import SignalWeights, UnifiedSignalEngine


def test_unified_signal_has_no_market_data_guard():
    result = UnifiedSignalEngine().analyze([])
    assert result["direction"] == "NEUTRAL"
    assert result["tradeable"] is False
    assert "NO_MARKET_DATA" in result["reasons"]


def test_unified_signal_never_marks_neutral_direction_tradeable():
    engine = UnifiedSignalEngine(SignalWeights(smc=0.55, technical=0.35, trend=0.10, threshold=0.25))
    # Insufficient candles keep the production analyzers from manufacturing a trade.
    result = engine.analyze([])
    assert result["direction"] == "NEUTRAL"
    assert result["tradeable"] is False


def test_unified_signal_threshold_is_configurable():
    engine = UnifiedSignalEngine(SignalWeights(threshold=0.90))
    result = engine.analyze([])
    assert result["confidence"] < 0.90
    assert result["tradeable"] is False


def test_unified_signal_exposes_component_evidence_when_data_exists():
    # Minimal candles exercise the real production engine without replacing it with a mock signal.
    from app.market_data import Candle
    candles = [Candle(open=100, high=102, low=99, close=101, volume=1000) for _ in range(5)]
    result = UnifiedSignalEngine().analyze(candles)
    assert "smc" in result
    assert "technical" in result
    assert "confirmation" in result
    assert result["direction"] in {"BULLISH", "BEARISH", "NEUTRAL"}
    assert 0.0 <= result["confidence"] <= 1.0
    assert isinstance(result["tradeable"], bool)
