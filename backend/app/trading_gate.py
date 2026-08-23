from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradingGate:
    """Small synchronous gate that prevents execution while recovery is unsafe."""

    def require_ready(self, trading_halted: bool) -> None:
        if trading_halted:
            raise RuntimeError("TRADING_HALTED")
