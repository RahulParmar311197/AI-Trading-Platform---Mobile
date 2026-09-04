from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

from app.confluence import score
from app.market_data import Candle, validate_candle_sequence, validate_freshness
from app.mtf_engine import confirm


@dataclass(frozen=True)
class TradeSignal:
    action: str
    entry: float
    stop_loss: float
    target: float
    risk_reward: float
    confidence: float
    reason: list[str]


def _valid_threshold(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _finite_non_negative(value: float, name: str) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite and non-negative") from exc
    if not isfinite(normalized) or normalized < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return normalized


def generate_signal(
    candles: list[Candle],
    min_score: int = 2,
    htf_candles: list[Candle] | None = None,
    require_mtf: bool = False,
    max_age_seconds: float | None = None,
    now: datetime | None = None,
) -> TradeSignal | None:
    """Generate a deterministic candidate signal; never authorizes broker execution."""
    min_score = _valid_threshold(min_score, "min_score")
    if not isinstance(require_mtf, bool):
        raise ValueError("require_mtf must be boolean")
    if max_age_seconds is not None:
        max_age_seconds = _finite_non_negative(max_age_seconds, "max_age_seconds")

    if len(candles) < 20 or not validate_candle_sequence(candles, now=now):
        return None
    if max_age_seconds is not None and not validate_freshness(
        candles[-1].timestamp, max_age_seconds=max_age_seconds, now=now
    ).fresh:
        return None

    if htf_candles is not None:
        if len(htf_candles) < 2 or not validate_candle_sequence(htf_candles, now=now):
            return None
        if max_age_seconds is not None and not validate_freshness(
            htf_candles[-1].timestamp, max_age_seconds=max_age_seconds, now=now
        ).fresh:
            return None
        if (
            candles[-1].symbol.strip().upper() != htf_candles[-1].symbol.strip().upper()
        ):
            return None

    result = score(candles)
    if not isinstance(result, dict):
        return None
    bias = result.get("bias")
    raw_score = result.get("score")
    try:
        total_base = float(raw_score)
    except (TypeError, ValueError):
        return None
    if not isfinite(total_base) or bias not in {"BULLISH", "BEARISH"}:
        return None

    reasons = list(result.get("reasons") or [])
    mtf_score = 0.0
    if htf_candles is not None:
        mtf = confirm(htf_candles, candles)
        if mtf.htf_bias not in {"BULLISH", "BEARISH", "NEUTRAL"} or mtf.ltf_bias not in {
            "BULLISH", "BEARISH", "NEUTRAL"
        }:
            return None
        reasons.append(f"MTF: {mtf.htf_bias} HTF / {mtf.ltf_bias} LTF")
        if not mtf.aligned:
            if require_mtf:
                return None
            if mtf.htf_bias in ("BULLISH", "BEARISH") and mtf.htf_bias != bias:
                return None
        else:
            try:
                mtf_component = float(mtf.score)
            except (TypeError, ValueError):
                return None
            if not isfinite(mtf_component):
                return None
            mtf_score = mtf_component if mtf.htf_bias == bias else -mtf_component
            reasons.append("HTF/LTF structure aligned")

    total = total_base + mtf_score
    if not isfinite(total) or abs(total) < min_score:
        return None

    last = float(candles[-1].close)
    raw_atr = result.get("atr")
    try:
        atr_value = float(raw_atr) if raw_atr is not None else float(candles[-1].high - candles[-1].low)
    except (TypeError, ValueError):
        return None
    if not isfinite(last) or not isfinite(atr_value) or atr_value <= 0:
        return None

    if bias == "BULLISH":
        entry, stop, target, action = last, last - 1.5 * atr_value, last + 3 * atr_value, "BUY"
    else:
        entry, stop, target, action = last, last + 1.5 * atr_value, last - 3 * atr_value, "SELL"

    risk = abs(entry - stop)
    reward = abs(target - entry)
    if not all(isfinite(x) for x in (entry, stop, target, risk, reward)) or risk <= 0:
        return None
    risk_reward = reward / risk
    confidence = min(0.99, 0.5 + abs(total) * 0.07)
    if not isfinite(risk_reward) or not isfinite(confidence):
        return None
    return TradeSignal(action, entry, stop, target, risk_reward, confidence, reasons)
