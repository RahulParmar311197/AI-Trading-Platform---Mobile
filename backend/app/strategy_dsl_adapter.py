"""Bridge from the canonical Strategy DSL to existing deterministic engines.

This adapter intentionally does not place orders. It only turns a validated
strategy definition into an immutable evaluation plan that downstream signal,
risk and backtest services can consume.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.strategy_dsl import StrategyDefinition, validate_strategy, strategy_to_dict


@dataclass(frozen=True)
class StrategyEvaluationPlan:
    strategy: dict[str, Any]
    required_timeframes: tuple[str, ...]
    condition_types: tuple[str, ...]
    risk: dict[str, Any]


def compile_strategy(strategy: StrategyDefinition) -> StrategyEvaluationPlan:
    validate_strategy(strategy)
    payload = strategy_to_dict(strategy)
    timeframes = tuple(sorted({c["timeframe"] for c in payload["conditions"] if c["timeframe"]}))
    condition_types = tuple(sorted({c["type"] for c in payload["conditions"]}))
    return StrategyEvaluationPlan(
        strategy=payload,
        required_timeframes=timeframes,
        condition_types=condition_types,
        risk=payload["risk"],
    )


def compile_strategy_payload(payload: dict[str, Any]) -> StrategyEvaluationPlan:
    """Compile only the canonical serialized representation.

    This function deliberately rejects unknown top-level fields only after
    extracting the allowed schema, preventing arbitrary data from becoming
    executable strategy configuration.
    """
    from app.strategy_dsl import ConditionType, Operator, RiskConfig, StrategyCondition

    conditions = tuple(
        StrategyCondition(
            type=ConditionType(item["type"]),
            operator=Operator(item["operator"]) if item.get("operator") else None,
            value=item.get("value"),
            timeframe=item.get("timeframe"),
            parameters=dict(item.get("parameters") or {}),
        )
        for item in payload.get("conditions", [])
    )
    risk_data = payload.get("risk") or {}
    strategy = StrategyDefinition(
        name=str(payload.get("name", "")),
        direction=str(payload.get("direction", "")),
        conditions=conditions,
        entry=str(payload.get("entry", "")),
        risk=RiskConfig(
            max_risk_percent=float(risk_data.get("max_risk_percent", 0)),
            minimum_rr=float(risk_data.get("minimum_rr", 0)),
            max_positions=int(risk_data.get("max_positions", 0)),
        ),
        version=int(payload.get("version", 1)),
    )
    return compile_strategy(strategy)
