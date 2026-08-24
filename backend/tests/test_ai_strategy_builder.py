import pytest

from app.ai_strategy_builder import StrategyParseError, build_from_structured, parse_simple_request


def test_natural_language_smc_request_becomes_validated_dsl():
    strategy = parse_simple_request(
        "Buy when liquidity sweep then bullish MSS and 5m FVG with RR 2 and risk 0.5%"
    )
    assert strategy.direction == "bullish"
    assert strategy.risk.minimum_rr == 2
    assert strategy.risk.max_risk_percent == 0.5
    assert {c.type.value for c in strategy.conditions} >= {"liquidity_sweep", "mss", "fvg"}


def test_structured_provider_payload_is_validated():
    strategy = build_from_structured({
        "name": "FVG Retest",
        "direction": "bullish",
        "conditions": [
            {"type": "fvg", "timeframe": "5m"},
            {"type": "mss", "timeframe": "5m"},
        ],
        "entry": "signal_confirmation",
        "risk": {"max_risk_percent": 0.5, "minimum_rr": 2, "max_positions": 1},
    })
    assert strategy.name == "FVG Retest"


def test_unsupported_request_fails_closed():
    with pytest.raises(StrategyParseError):
        parse_simple_request("Predict tomorrow's market using anything you can find")
