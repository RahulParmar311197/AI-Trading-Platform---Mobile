"""Deterministic setup-level analytics with read-only AI feedback."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from collections import defaultdict
from typing import Any
from app.ai_provider import AIProvider

SETUP_CONTRACT = """Analyze ONLY supplied setup statistics. Never invent facts. Return JSON keys: summary, strengths, weaknesses, improvement_candidates. Suggestions are advisory only."""

@dataclass(frozen=True)
class SetupStats:
    key: str
    trades: int
    wins: int
    losses: int
    win_rate: float
    net_pnl: float
    expectancy: float

class AISetupAnalytics:
    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider

    def analyze(self, trades: list[dict[str, Any]]) -> dict[str, Any]:
        groups: dict[str, list[float]] = defaultdict(list)
        for trade in trades:
            if not isinstance(trade, dict):
                continue
            pnl = trade.get("pnl")
            if isinstance(pnl, (int, float)):
                groups[self._key(trade)].append(float(pnl))
        setups = [self._stats(k, v) for k, v in sorted(groups.items())]
        feedback = self._feedback(setups) if self.provider else {"summary":"Deterministic setup-level report.","strengths":[],"weaknesses":[],"improvement_candidates":[]}
        return {"setups": [asdict(s) for s in setups], "feedback": feedback}

    @staticmethod
    def _key(t: dict[str, Any]) -> str:
        return "|".join(str(t.get(k, "unknown")) for k in ("strategy", "direction", "timeframe", "session", "setup"))

    @staticmethod
    def _stats(key: str, pnls: list[float]) -> SetupStats:
        wins = sum(p > 0 for p in pnls); losses = sum(p < 0 for p in pnls); n = len(pnls); net = sum(pnls)
        return SetupStats(key, n, wins, losses, wins / n if n else 0.0, net, net / n if n else 0.0)

    def _feedback(self, setups: list[SetupStats]) -> dict[str, Any]:
        import json
        result = self.provider.generate_structured(SETUP_CONTRACT, json.dumps([asdict(s) for s in setups]))
        keys = ("summary", "strengths", "weaknesses", "improvement_candidates")
        if any(k not in result for k in keys):
            raise ValueError("incomplete setup feedback")
        return result
