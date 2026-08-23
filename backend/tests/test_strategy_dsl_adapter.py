import pytest

from app.strategy_dsl import ConditionType, RiskConfig, StrategyCondition, StrategyDefinition
from app.strategy_dsl_adapter import compile_strategy, compile_strategy_payload


def strategy():
    return StrategyDefinition(
        name="SMC FVG",
        direction="both",
        conditions=(
            StrategyCondition(ConditionType.FVG, timeframe="5m"),
            StrategyCondition(ConditionType.LIQUIDITY_SWEEP, timeframe="15m"),
        ),
        entry="fvg_retest",
        risk=RiskConfig(max_risk_percent=0.5, minimum_rr=2),
    )


def test_compile_strategy_extracts_execution_requirements():
    plan = compile_strategy(strategy())
    assert plan.required_timeframes == ("15m", "5m")
    assert plan.condition_types == ("fvg", "liquidity_sweep")
    assert plan.risk["minimum_rr"] == 2


def test_serialized_strategy_round_trip():
    plan = compile_strategy(strategy())
    restored = compile_strategy_payload(plan.strategy)
    assert restored.strategy == plan.strategy


def test_invalid_serialized_strategy_is_rejected():
    payload = {
        "name": "bad",
        "direction": "bullish",
        "conditions": [{"type": "FVG", "timeframe": "2m"}],
        "entry": "x",
        "risk": {"max_risk_percent": 0.5, "minimum_rr": 2, "max_positions": 1},
    }
    with pytest.raises((ValueError, KeyError)):
        compile_strategy_payload(payload)
