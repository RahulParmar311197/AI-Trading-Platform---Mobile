"""Grounded trading research workspace; AI is an evidence synthesizer, not an authority."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from app.ai_provider import AIProvider

RESEARCH_CONTRACT = """You are a trading research assistant. Use ONLY the supplied evidence packet.
Never invent prices, news, indicators, SMC/ICT events, or performance. Distinguish facts
from hypotheses. Return JSON keys: answer, evidence, uncertainties, follow_up_data.
Do not place orders or modify strategies."""

@dataclass(frozen=True)
class ResearchResult:
    question: str
    answer: str
    evidence: tuple[str, ...]
    uncertainties: tuple[str, ...]
    follow_up_data: tuple[str, ...]
    evidence_packet: dict[str, Any]

class AIResearchError(RuntimeError):
    pass

class AIResearchAssistant:
    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider

    def research(self, question: str, evidence_packet: dict[str, Any]) -> ResearchResult:
        if not question.strip():
            raise AIResearchError("research question is required")
        if not isinstance(evidence_packet, dict) or not evidence_packet:
            raise AIResearchError("evidence packet is required")
        if self.provider is None:
            return ResearchResult(question, "Research provider is not configured; evidence was not interpreted by AI.", tuple(map(str, evidence_packet.get("facts", []))), ("AI provider unavailable",), ("Provide current market and strategy evidence",), evidence_packet)
        try:
            import json
            result = self.provider.generate_structured(RESEARCH_CONTRACT, json.dumps({"question": question, "evidence": evidence_packet}, default=str))
            keys = ("answer", "evidence", "uncertainties", "follow_up_data")
            if any(k not in result for k in keys):
                raise AIResearchError("incomplete research response")
            return ResearchResult(question, str(result["answer"]), tuple(map(str,result["evidence"])), tuple(map(str,result["uncertainties"])), tuple(map(str,result["follow_up_data"])), evidence_packet)
        except AIResearchError:
            raise
        except Exception as exc:
            raise AIResearchError(f"research failed: {exc}") from exc
