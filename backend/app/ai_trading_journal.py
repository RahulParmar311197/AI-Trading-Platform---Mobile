"""Deterministic post-trade journal and AI learning feedback boundary."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from app.ai_provider import AIProvider

JOURNAL_CONTRACT = """Analyze ONLY the supplied completed trade record. Do not invent facts.
Return JSON keys: outcome_summary, what_worked, what_failed, lessons, rule_change_candidates.
Rule change candidates are suggestions only; never apply or authorize them."""

@dataclass(frozen=True)
class JournalEntry:
    trade_id: str
    decision: str
    outcome: str
    expected: dict[str, Any]
    actual: dict[str, Any]
    explanation: dict[str, Any]

class AITradingJournal:
    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider

    def create_entry(self, record: dict[str, Any]) -> JournalEntry:
        required = {"trade_id", "decision", "expected", "actual"}
        if not isinstance(record, dict) or not required.issubset(record):
            raise ValueError("trade_id, decision, expected and actual are required")
        expected, actual = record["expected"], record["actual"]
        outcome = self._outcome(expected, actual)
        explanation = self._feedback(record, outcome) if self.provider else {
            "outcome_summary": f"Trade outcome: {outcome}.",
            "what_worked": [], "what_failed": [], "lessons": [],
            "rule_change_candidates": [],
        }
        return JournalEntry(str(record["trade_id"]), str(record["decision"]), outcome, expected, actual, explanation)

    @staticmethod
    def _outcome(expected: dict[str, Any], actual: dict[str, Any]) -> str:
        if actual.get("status") in {"OPEN", "CANCELLED", "REJECTED"}:
            return str(actual["status"])
        pnl = actual.get("pnl")
        if isinstance(pnl, (int, float)):
            return "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "BREAKEVEN"
        return "UNKNOWN"

    def _feedback(self, record: dict[str, Any], outcome: str) -> dict[str, Any]:
        import json
        payload = dict(record)
        payload["derived_outcome"] = outcome
        result = self.provider.generate_structured(JOURNAL_CONTRACT, json.dumps(payload, default=str))
        keys = ("outcome_summary", "what_worked", "what_failed", "lessons", "rule_change_candidates")
        if any(k not in result for k in keys):
            raise ValueError("incomplete journal feedback")
        return result
