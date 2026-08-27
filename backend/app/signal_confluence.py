"""Deterministic signal-confluence layer.

This module converts independent analysis evidence into an advisory signal. It
never places orders; risk and execution remain downstream responsibilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ConfluenceConfig:
    min_score: float = 0.60
    ict_weight: float = 0.60
    technical_weight: float = 0.40

    def __post_init__(self) -> None:
        if not 0 <= self.min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")
        if self.ict_weight < 0 or self.technical_weight < 0:
            raise ValueError("weights must be non-negative")
        if self.ict_weight + self.technical_weight <= 0:
            raise ValueError("at least one confluence weight is required")


@dataclass(frozen=True)
class SignalDecision:
    action: str
    score: float
    direction: str | None
    reasons: tuple[str, ...]
    components: Mapping[str, float]


def _direction_score(value: Any) -> tuple[str | None, float]:
    if isinstance(value, str):
        value = value.upper()
        if value in {"BULLISH", "LONG", "BUY"}:
            return "LONG", 1.0
        if value in {"BEARISH", "SHORT", "SELL"}:
            return "SHORT", 1.0
    return None, 0.0


def evaluate_confluence(
    ict: Mapping[str, Any] | None = None,
    technical: Mapping[str, Any] | None = None,
    config: ConfluenceConfig | None = None,
) -> SignalDecision:
    """Score ICT/SMC and technical evidence without producing an order.

    Evidence is intentionally tolerant: absent indicators contribute zero
    rather than fabricating a directional signal.
    """
    cfg = config or ConfluenceConfig()
    ict = ict or {}
    technical = technical or {}
    reasons: list[str] = []

    ict_direction, ict_score = _direction_score(ict.get("bias") or ict.get("choch") or ict.get("bos"))
    tech_direction, tech_score = _direction_score(
        technical.get("direction") or technical.get("bias") or technical.get("signal")
    )

    if ict_direction:
        reasons.append(f"ICT bias {ict_direction}")
    if tech_direction:
        reasons.append(f"technical bias {tech_direction}")

    total_weight = cfg.ict_weight + cfg.technical_weight
    weighted = (ict_score * cfg.ict_weight + tech_score * cfg.technical_weight) / total_weight
    direction: str | None = None
    if ict_direction and tech_direction and ict_direction == tech_direction:
        direction = ict_direction
        weighted = min(1.0, weighted + 0.20)
        reasons.append("ICT and technical direction agree")
    elif ict_direction and not tech_direction:
        direction = ict_direction
    elif tech_direction and not ict_direction:
        direction = tech_direction
    else:
        reasons.append("no directional agreement")

    action = "HOLD"
    if direction and weighted >= cfg.min_score:
        action = "BUY" if direction == "LONG" else "SELL"
    else:
        reasons.append("confluence threshold not met")

    return SignalDecision(
        action=action,
        score=round(weighted, 6),
        direction=direction,
        reasons=tuple(reasons),
        components={"ict": round(ict_score, 6), "technical": round(tech_score, 6)},
    )


__all__ = ["ConfluenceConfig", "SignalDecision", "evaluate_confluence"]
