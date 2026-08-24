"""Safe natural-language strategy builder.

This module deliberately performs schema extraction, not code generation.
An LLM/provider can later supply the structured candidate, while this module
normalizes and validates it before any trading component sees it.
"""
from __future__ import annotations

import re
from typing import Any

from app.strategy_dsl import (
    ConditionType,
    Operator,
    RiskConfig,
    StrategyCondition,
    StrategyDefinition,
    validate_strategy,
)


class StrategyParseError(ValueError):
    pass


_CONDITION_ALIASES = {
    "liquidity sweep": ConditionType.LIQUIDITY_SWEEP,
    "liquidity_sweep": ConditionType.LIQUIDITY_SWEEP,
    "mss": ConditionType.MSS,
    "market structure shift": ConditionType.MSS,
    "bos": ConditionType.BOS,
    "break of structure": ConditionType.BOS,
    "choch": ConditionType.CHOCH,
    "fvg": ConditionType.FVG,
    "fair value gap": ConditionType.FVG,
    "order block": ConditionType.ORDER_BLOCK,
    "order_block": ConditionType.ORDER_BLOCK,
    "premium discount": ConditionType.PREMIUM_DISCOUNT,
}


def build_from_structured(payload: dict[str, Any]) -> StrategyDefinition:
    """Convert a provider-neutral structured candidate into the canonical DSL."""
    try:
        conditions = tuple(
            StrategyCondition(
                type=ConditionType(str(item["type"])),
                operator=Operator(str(item["operator"])) if item.get("operator") else None,
                value=item.get("value"),
                timeframe=item.get("timeframe"),
                parameters=dict(item.get("parameters") or {}),
            )
            for item in payload.get("conditions", [])
        )
        risk = payload.get("risk") or {}
        strategy = StrategyDefinition(
            name=str(payload.get("name") or "AI Strategy"),
            direction=str(payload.get("direction") or "both"),
            conditions=conditions,
            entry=str(payload.get("entry") or "signal_confirmation"),
            risk=RiskConfig(
                max_risk_percent=float(risk.get("max_risk_percent", 0.5)),
                minimum_rr=float(risk.get("minimum_rr", 2.0)),
                max_positions=int(risk.get("max_positions", 1)),
            ),
            version=int(payload.get("version", 1)),
        )
        return validate_strategy(strategy)
    except (KeyError, TypeError, ValueError) as exc:
        raise StrategyParseError(f"invalid strategy candidate: {exc}") from exc


def parse_simple_request(text: str) -> StrategyDefinition:
    """Parse common SMC/ICT requests without executing arbitrary text.

    This is intentionally conservative. Unsupported natural-language requests
    fail with a clear error instead of guessing a trade rule.
    """
    raw = text.strip()
    lower = raw.lower()
    if not raw:
        raise StrategyParseError("strategy request is empty")

    found: list[StrategyCondition] = []
    for alias, condition_type in sorted(_CONDITION_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in lower and all(c.type != condition_type for c in found):
            timeframe_match = re.search(r"(\d+\s*(?:m|h|d|w))", lower)
            timeframe = timeframe_match.group(1).replace(" ", "") if timeframe_match else None
            if timeframe == "d": timeframe = "1D"
            if timeframe == "w": timeframe = "1W"
            found.append(StrategyCondition(condition_type, timeframe=timeframe))

    if not found:
        raise StrategyParseError("no supported SMC/ICT strategy condition found")

    direction = "bearish" if any(x in lower for x in ("sell", "short", "bearish")) else "bullish" if any(x in lower for x in ("buy", "long", "bullish")) else "both"
    rr_match = re.search(r"(?:rr|risk.?reward|r:r)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)", lower)
    rr = float(rr_match.group(1)) if rr_match else 2.0
    risk_match = re.search(r"(?:risk)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*%", lower)
    risk_pct = float(risk_match.group(1)) if risk_match else 0.5

    strategy = StrategyDefinition(
        name="Natural Language SMC/ICT Strategy",
        direction=direction,
        conditions=tuple(found),
        entry="signal_confirmation",
        risk=RiskConfig(max_risk_percent=risk_pct, minimum_rr=rr),
    )
    return validate_strategy(strategy)
