"""Canonical, deterministic strategy DSL.

The DSL is intentionally data-only: it can be produced by an AI layer, but it
cannot contain executable Python/code. Validation happens before a strategy can
reach the trading engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConditionType(str, Enum):
    TREND = "trend"
    BOS = "bos"
    MSS = "mss"
    CHOCH = "choch"
    LIQUIDITY_SWEEP = "liquidity_sweep"
    FVG = "fvg"
    ORDER_BLOCK = "order_block"
    PREMIUM_DISCOUNT = "premium_discount"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    SESSION = "session"
    INDICATOR = "indicator"
    OPTIONS_IV = "options_iv"
    OPTIONS_OI = "options_oi"
    OPTIONS_GREEKS = "options_greeks"


class Operator(str, Enum):
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN = "LESS_THAN"
    CROSSES = "CROSSES"
    TOUCHES = "TOUCHES"
    WITHIN = "WITHIN"


@dataclass(frozen=True)
class StrategyCondition:
    type: ConditionType
    operator: Operator | None = None
    value: Any = None
    timeframe: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RiskConfig:
    max_risk_percent: float = 0.5
    minimum_rr: float = 2.0
    max_positions: int = 1


@dataclass(frozen=True)
class StrategyDefinition:
    name: str
    direction: str
    conditions: tuple[StrategyCondition, ...]
    entry: str
    risk: RiskConfig = field(default_factory=RiskConfig)
    version: int = 1


class StrategyValidationError(ValueError):
    pass


_ALLOWED_TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1D", "1W"}
_ALLOWED_DIRECTIONS = {"bullish", "bearish", "both"}


def validate_strategy(strategy: StrategyDefinition) -> StrategyDefinition:
    if not strategy.name.strip():
        raise StrategyValidationError("strategy name is required")
    if strategy.direction.lower() not in _ALLOWED_DIRECTIONS:
        raise StrategyValidationError("direction must be bullish, bearish, or both")
    if not strategy.conditions:
        raise StrategyValidationError("at least one condition is required")
    if not strategy.entry.strip():
        raise StrategyValidationError("entry rule is required")
    if not 0 < strategy.risk.max_risk_percent <= 100:
        raise StrategyValidationError("max_risk_percent must be greater than 0 and at most 100")
    if strategy.risk.minimum_rr <= 0:
        raise StrategyValidationError("minimum_rr must be greater than zero")
    if strategy.risk.max_positions < 1:
        raise StrategyValidationError("max_positions must be at least 1")
    for condition in strategy.conditions:
        if condition.timeframe and condition.timeframe not in _ALLOWED_TIMEFRAMES:
            raise StrategyValidationError(f"unsupported timeframe: {condition.timeframe}")
        if condition.type in {ConditionType.OPTIONS_IV, ConditionType.OPTIONS_OI, ConditionType.OPTIONS_GREEKS}:
            continue
        if condition.type == ConditionType.INDICATOR and not condition.parameters.get("name"):
            raise StrategyValidationError("indicator condition requires parameters.name")
    return strategy


def strategy_to_dict(strategy: StrategyDefinition) -> dict[str, Any]:
    validate_strategy(strategy)
    return {
        "version": strategy.version,
        "name": strategy.name,
        "direction": strategy.direction.lower(),
        "conditions": [
            {
                "type": c.type.value,
                "operator": c.operator.value if c.operator else None,
                "value": c.value,
                "timeframe": c.timeframe,
                "parameters": c.parameters,
            }
            for c in strategy.conditions
        ],
        "entry": strategy.entry,
        "risk": {
            "max_risk_percent": strategy.risk.max_risk_percent,
            "minimum_rr": strategy.risk.minimum_rr,
            "max_positions": strategy.risk.max_positions,
        },
    }
