import pytest

from app.ai_provider import AIStrategyService, AIProviderError


class FakeProvider:
    def generate_structured(self, system_prompt, user_prompt):
        assert "JSON only" in system_prompt
        return {
            "name": "AI FVG",
            "direction": "bullish",
            "conditions": [
                {"type": "liquidity_sweep", "timeframe": "15m"},
                {"type": "mss", "timeframe": "5m"},
                {"type": "fvg", "timeframe": "5m"},
            ],
            "entry": "fvg_retest",
            "risk": {"max_risk_percent": 0.5, "minimum_rr": 2, "max_positions": 1},
        }


def test_provider_output_is_validated_before_return():
    result = AIStrategyService(FakeProvider(), "test").build("build an FVG strategy")
    assert result.strategy.name == "AI FVG"
    assert result.provider == "test"


def test_local_fallback_is_conservative():
    result = AIStrategyService().build("buy after liquidity sweep and bullish MSS with 5m FVG RR 2")
    assert result.strategy.direction == "bullish"


def test_invalid_ai_output_fails_closed():
    class BadProvider:
        def generate_structured(self, *_):
            return {"name": "bad", "direction": "bullish", "conditions": [], "entry": "x"}

    with pytest.raises(AIProviderError):
        AIStrategyService(BadProvider(), "bad").build("make strategy")
