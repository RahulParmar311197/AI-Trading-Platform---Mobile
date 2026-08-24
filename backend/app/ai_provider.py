"""Provider-neutral AI gateway with strict structured strategy output.

No provider SDK is required here. The application can inject a provider
implementation later (OpenAI or another compatible service) without letting
model output execute code or bypass deterministic validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.ai_strategy_builder import StrategyParseError, build_from_structured, parse_simple_request
from app.strategy_dsl import StrategyDefinition, strategy_to_dict


SYSTEM_CONTRACT = """You are a trading-strategy parser. Return JSON only.
Never return executable code. Use only supported Strategy DSL condition types.
Specify direction, conditions, entry, and risk. Do not invent market data.
"""


class AIProvider(Protocol):
    def generate_structured(self, system_prompt: str, user_prompt: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class AIStrategyResult:
    strategy: StrategyDefinition
    provider: str
    raw_candidate: dict[str, Any]


class AIProviderError(RuntimeError):
    pass


class AIStrategyService:
    def __init__(self, provider: AIProvider | None = None, provider_name: str = "deterministic"):
        self.provider = provider
        self.provider_name = provider_name

    def build(self, request: str) -> AIStrategyResult:
        if not request.strip():
            raise AIProviderError("strategy request is empty")

        if self.provider is None:
            # Safe local fallback; it is deliberately conservative.
            try:
                strategy = parse_simple_request(request)
            except StrategyParseError as exc:
                raise AIProviderError(str(exc)) from exc
            return AIStrategyResult(strategy, self.provider_name, strategy_to_dict(strategy))

        try:
            candidate = self.provider.generate_structured(SYSTEM_CONTRACT, request)
            strategy = build_from_structured(candidate)
            return AIStrategyResult(strategy, self.provider_name, candidate)
        except Exception as exc:
            raise AIProviderError(f"AI strategy generation failed: {exc}") from exc
