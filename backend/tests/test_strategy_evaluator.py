from app.market_data import Candle
from app.strategy_dsl import ConditionType, RiskConfig, StrategyCondition, StrategyDefinition
from app.strategy_evaluator import StrategyEvaluator


def candles():
    return [
        Candle(timestamp=i, open=100+i*0.05, high=101+i*0.05, low=99+i*0.05, close=100.5+i*0.05, volume=1000)
        for i in range(60)
    ]


def test_empty_market_data_fails_closed():
    strategy = StrategyDefinition(
        name="Trend",
        direction="both",
        conditions=(StrategyCondition(ConditionType.TREND),),
        entry="signal",
        risk=RiskConfig(),
    )
    result = StrategyEvaluator().evaluate(strategy, [])
    assert result.matched is False
    assert "NO_MARKET_DATA" in result.reasons


def test_evaluator_returns_structured_result():
    strategy = StrategyDefinition(
        name="Trend",
        direction="both",
        conditions=(StrategyCondition(ConditionType.TREND),),
        entry="signal",
        risk=RiskConfig(),
    )
    result = StrategyEvaluator().evaluate(strategy, candles())
    assert isinstance(result.matched, bool)
    assert 0 <= result.confidence <= 1
    assert result.strategy["name"] == "Trend"
