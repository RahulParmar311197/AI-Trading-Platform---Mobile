"""Grounded explanations for accepted/rejected trade candidates."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from app.ai_provider import AIProvider

EXPLAINER_CONTRACT = """Explain ONLY the supplied trade decision record. Never invent market facts.
Return JSON keys: decision, summary, evidence, risk_gates, invalidation, missing_data.
Do not create an order or change the decision."""

@dataclass(frozen=True)
class TradeExplanation:
    decision: str
    summary: str
    evidence: tuple[str, ...]
    risk_gates: tuple[str, ...]
    invalidation: tuple[str, ...]
    missing_data: tuple[str, ...]
    record: dict[str, Any]

class TradeExplanationError(RuntimeError):
    pass

class AITradeExplainer:
    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider

    def explain(self, record: dict[str, Any]) -> TradeExplanation:
        if not isinstance(record, dict) or not record:
            raise TradeExplanationError("trade decision record is required")
        if not {"decision", "signal", "risk"}.issubset(record):
            raise TradeExplanationError("record must contain decision, signal and risk")
        if self.provider is None:
            signal, risk = record["signal"], record["risk"]
            reasons = tuple(map(str, signal.get("reasons", []))) if isinstance(signal, dict) else ()
            gates = tuple(map(str, risk.get("gates", []))) if isinstance(risk, dict) else ()
            return TradeExplanation(str(record["decision"]), f"Decision: {record['decision']}.", reasons, gates, (), ("AI explanation provider is not configured.",), record)
        try:
            result = self.provider.generate_structured(EXPLAINER_CONTRACT, str(record))
            keys = ("decision", "summary", "evidence", "risk_gates", "invalidation", "missing_data")
            if any(k not in result for k in keys):
                raise TradeExplanationError("incomplete explanation")
            if str(result["decision"]).upper() != str(record["decision"]).upper():
                raise TradeExplanationError("provider attempted to change trade decision")
            return TradeExplanation(str(result["decision"]), str(result["summary"]), tuple(map(str,result["evidence"])), tuple(map(str,result["risk_gates"])), tuple(map(str,result["invalidation"])), tuple(map(str,result["missing_data"])), record)
        except TradeExplanationError:
            raise
        except Exception as exc:
            raise TradeExplanationError(f"trade explanation failed: {exc}") from exc
