"""Deterministic strategy-performance analytics with AI suggestions as a read-only layer."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from app.ai_provider import AIProvider

PERFORMANCE_CONTRACT = """Analyze ONLY the supplied aggregate trading statistics. Never invent data.
Return JSON keys: summary, strengths, weaknesses, improvement_candidates.
Suggestions are advisory only and must never modify trading rules."""

@dataclass(frozen=True)
class PerformanceReport:
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    net_pnl: float
    expectancy: float
    max_drawdown: float
    feedback: dict[str, Any]

class AIPerformanceAnalytics:
    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider

    def analyze(self, trades: list[dict[str, Any]]) -> PerformanceReport:
        pnls = [float(t.get("pnl", 0)) for t in trades if isinstance(t, dict)]
        wins = sum(p > 0 for p in pnls); losses = sum(p < 0 for p in pnls); be = sum(p == 0 for p in pnls)
        total = len(pnls); net = sum(pnls)
        equity = peak = drawdown = 0.0
        for pnl in pnls:
            equity += pnl; peak = max(peak, equity); drawdown = max(drawdown, peak - equity)
        stats = {"total_trades": total, "wins": wins, "losses": losses, "breakeven": be, "win_rate": wins / total if total else 0.0, "net_pnl": net, "expectancy": net / total if total else 0.0, "max_drawdown": drawdown}
        feedback = self._feedback(stats) if self.provider else {"summary":"Deterministic performance report.","strengths":[],"weaknesses":[],"improvement_candidates":[]}
        return PerformanceReport(**stats, feedback=feedback)

    def _feedback(self, stats: dict[str, Any]) -> dict[str, Any]:
        import json
        result = self.provider.generate_structured(PERFORMANCE_CONTRACT, json.dumps(stats))
        keys = ("summary", "strengths", "weaknesses", "improvement_candidates")
        if any(k not in result for k in keys): raise ValueError("incomplete performance feedback")
        return result
