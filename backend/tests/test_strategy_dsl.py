import pytest

from app.strategy_dsl import (
    ConditionType,
    Operator,
    RiskConfig,
    StrategyCondition,
    StrategyDefinition,
    StrategyValidationError,
    strategy_to_dict,
    validate_strategy,
)


def valid_strategy():
    return StrategyDefinition(
        name="Liquidity Sweep FVG",
        direction="bullish",
        conditions=(
            StrategyCondition(
                type=ConditionType.LIQUIDITY_SWEEP,
                operator=Operator.TOUCHES,
                value="sell_side",
                timeframe="15m",
            ),
            StrategyCondition(
                type=ConditionType.MSS,
                value="bullish",
                timeframe="5m",
            ),
            StrategyCondition(
                type=ConditionType.FVG,
                value="bullish",
                timeframe="5m",
            ),
        ),
        entry="fvg_retest",
        risk=RiskConfig(max_risk_percent=0.5, minimum_rr=2.0),
    )


def test_valid_strategy_serializes_to_data_only_dict():
    result = strategy_to_dict(valid_strategy())
    assert result["direction"] == "bullish"
    assert result["conditions"][0]["type"] == "liquidity_sweep"
    assert result["risk"]["minimum_rr"] == 2.0


def test_invalid_direction_fails_closed():
    s = valid_strategy()
    with pytest.raises(StrategyValidationError):
        validate_strategy(StrategyDefinition(s.name, "LONG", s.conditions, s.entry, s.risk))


def test_invalid_risk_fails_closed():
    s = valid_strategy()
    with pytest.raises(StrategyValidationError):
        validate_strategy(StrategyDefinition(s.name, s.direction, s.conditions, s.entry, RiskConfig(0, 2)))


def test_invalid_timeframe_fails_closed():
    s = valid_strategy()
    conditions = (StrategyCondition(ConditionType.MSS, timeframe="10m"),)
    with pytest.raises(StrategyValidationError):
        validate_strategy(StrategyDefinition(s.name, s.direction, conditions, s.entry, s.risk))


def test_indicator_requires_name():
    s = valid_strategy()
    conditions = (StrategyCondition(ConditionType.INDICATOR, parameters={}),)
    with pytest.raises(StrategyValidationError):
        validate_strategy(StrategyDefinition(s.name, s.direction, conditions, s.entry, s.risk))
