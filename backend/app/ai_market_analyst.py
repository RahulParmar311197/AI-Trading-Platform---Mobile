"""Grounded AI market-analysis layer.

The model receives a serialized snapshot produced by deterministic engines.
It must explain that snapshot; it is not allowed to manufacture prices,
indicators, SMC/ICT events, or trading actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai_provider import AIProvider
from app.market_data import Candle
from app.unified_signal import UnifiedSignalEngine


ANALYST_CONTRACT = """You are a market-analysis explainer. Use ONLY the supplied market snapshot.
Never invent prices, indicators, SMC/ICT events, news, or market facts.
Do not place or recommend an order. Explain evidence, uncertainty, invalidation,
and what additional data would be needed. Return concise JSON with keys:
summary, bias, evidence, risks, missing_data."""


@dataclass(frozen=True)
class MarketAnalysis:
    summary: str
    bias: str
    evidence: tuple[str, ...]
    risks: tuple[str, ...]
    missing_data: tuple[str, ...]
    grounded_snapshot: dict[str, Any]


class MarketAnalystError(RuntimeError):
    pass


class AIMarketAnalyst:
    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider
        self.signal_engine = UnifiedSignalEngine()

    def snapshot(self, candles: list[Candle]) -> dict[str, Any]:
        signal = self.signal_engine.analyze(candles)
        return {
            "candle_count": len(candles),
            "latest_timestamp": candles[-1].timestamp if candles else None,
            "signal": self._json_safe(signal),
        }

    def analyze(self, candles: list[Candle]) -> MarketAnalysis:
        snapshot = self.snapshot(candles)
        if self.provider is None:
            signal = snapshot["signal"]
            return MarketAnalysis(
                summary=f"Deterministic bias is {signal['direction']} with confidence {signal['confidence']:.2f}.",
                bias=signal["direction"],
                evidence=tuple(signal.get("reasons", [])),
                risks=("AI explanation provider is not configured.", "Signal confidence is not a guarantee."),
                missing_data=("news/fundamental context", "external macro context"),
                grounded_snapshot=snapshot,
            )
        try:
            result = self.provider.generate_structured(ANALYST_CONTRACT, str(snapshot))
            required = ("summary", "bias", "evidence", "risks", "missing_data")
            if any(k not in result for k in required):
                raise MarketAnalystError("provider returned incomplete analyst output")
            return MarketAnalysis(
                summary=str(result["summary"]), bias=str(result["bias"]),
                evidence=tuple(map(str, result["evidence"])),
                risks=tuple(map(str, result["risks"])),
                missing_data=tuple(map(str, result["missing_data"])),
                grounded_snapshot=snapshot,
            )
        except MarketAnalystError:
            raise
        except Exception as exc:
            raise MarketAnalystError(f"market analysis failed: {exc}") from exc

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(k): AIMarketAnalyst._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [AIMarketAnalyst._json_safe(v) for v in value]
        if hasattr(value, "__dict__"):
            return AIMarketAnalyst._json_safe(vars(value))
        return str(value)
