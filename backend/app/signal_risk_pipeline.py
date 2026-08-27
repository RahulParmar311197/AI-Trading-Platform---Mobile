"""Safe signal-to-risk boundary.

Confluence creates an advisory decision; this adapter is the only place that
turns an actionable signal into a risk-gateway authorization request.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.order_intent import OrderIntent
from app.risk_gateway import RiskGatewayResult, authorize
from app.risk_engine import RiskLimits
from app.signal_confluence import SignalDecision, evaluate_confluence


@dataclass(frozen=True)
class SignalRiskResult:
    signal: SignalDecision
    authorization: RiskGatewayResult | None


def evaluate_and_authorize(
    *,
    ict: Mapping[str, Any] | None = None,
    technical: Mapping[str, Any] | None = None,
    order: OrderIntent | None = None,
    equity: float,
    daily_pnl: float,
    open_positions: int,
    recent_losses: int = 0,
    limits: RiskLimits | None = None,
) -> SignalRiskResult:
    """Evaluate confluence and, only for an actionable signal, invoke RiskGateway.

    A HOLD signal never reaches authorization. An actionable signal without an
    order is rejected at this boundary rather than converted into an invented
    order.
    """
    signal = evaluate_confluence(ict=ict, technical=technical)
    if signal.action == "HOLD":
        return SignalRiskResult(signal=signal, authorization=None)
    if order is None:
        raise ValueError("an OrderIntent is required for an actionable signal")
    return SignalRiskResult(
        signal=signal,
        authorization=authorize(
            order=order,
            equity=equity,
            daily_pnl=daily_pnl,
            open_positions=open_positions,
            recent_losses=recent_losses,
            limits=limits,
        ),
    )


__all__ = ["SignalRiskResult", "evaluate_and_authorize"]
