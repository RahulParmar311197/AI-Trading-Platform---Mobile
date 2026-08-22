from __future__ import annotations
from app.ensemble_v2 import decide_v2
from app.market_data import Candle


def decide_mtf(frames: dict[str, list[Candle]]):
    decisions = {tf: decide_v2(c) for tf, c in frames.items() if len(c) >= 30}
    if not decisions:
        raise ValueError("at least one timeframe with 30 candles is required")
    weights = {"1d": 0.30, "4h": 0.25, "1h": 0.20, "15m": 0.15, "5m": 0.10, "1m": 0.05}
    total_weight = sum(weights.get(tf.lower(), 0.10) for tf in decisions)
    score = sum(d.score * weights.get(tf.lower(), 0.10) for tf, d in decisions.items()) / total_weight
    action = "BUY" if score >= 0.35 else "SELL" if score <= -0.35 else "NO_TRADE"
    confidence = abs(score)
    return {"action": action, "score": score, "confidence": confidence, "timeframes": {tf: d.__dict__ for tf, d in decisions.items()}}
