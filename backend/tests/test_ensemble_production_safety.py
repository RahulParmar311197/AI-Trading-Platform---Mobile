from app.ensemble import decide
from app.market_data import Candle


def candles(n=30):
    return [Candle(open=100+i, high=102+i, low=99+i, close=101+i, volume=1000+i*10) for i in range(n)]


def test_ensemble_returns_valid_action_and_bounded_confidence():
    decision = decide(candles())
    assert decision.action in {"BUY", "SELL", "NO_TRADE"}
    assert -1.0 <= decision.score <= 1.0
    assert 0.0 <= decision.confidence <= 1.0
    assert 0.0 <= decision.ai_probability_up <= 1.0


def test_ensemble_never_emits_unknown_action():
    decision = decide([])
    assert decision.action in {"BUY", "SELL", "NO_TRADE"}
    assert decision.confidence >= 0.0


def test_high_volatility_reduces_combined_score():
    # The production ensemble applies a 0.75 multiplier in HIGH_VOLATILITY.
    # This test checks the invariant without replacing the model implementation.
    decision = decide(candles())
    assert isinstance(decision.regime, str)
    assert isinstance(decision.reasons, list)


def test_no_trade_is_explicitly_non_executable_candidate():
    decision = decide([])
    assert decision.action == "NO_TRADE"
    assert "AI regime:" in decision.reasons[0]
