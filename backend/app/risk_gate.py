from __future__ import annotations

from dataclasses import dataclass

from app.broker_adapter import BrokerOrderRequest


@dataclass(frozen=True)
class RiskLimits:
    max_order_quantity: float
    max_position_quantity: float
    max_daily_loss: float
    max_trade_loss: float


@dataclass(frozen=True)
class RiskSnapshot:
    position_quantity: float = 0.0
    daily_pnl: float = 0.0
    projected_trade_loss: float = 0.0
    kill_switch: bool = False
    broker_ready: bool = False


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str


class PreTradeRiskGate:
    """Fail-closed authorization immediately before broker submission."""

    def __init__(self, limits: RiskLimits):
        if limits.max_order_quantity <= 0 or limits.max_position_quantity <= 0:
            raise ValueError("risk quantity limits must be positive")
        if limits.max_daily_loss < 0 or limits.max_trade_loss < 0:
            raise ValueError("risk loss limits cannot be negative")
        self.limits = limits

    def evaluate(self, request: BrokerOrderRequest, snapshot: RiskSnapshot) -> RiskDecision:
        if snapshot.kill_switch:
            return RiskDecision(False, "RISK_KILL_SWITCH_ACTIVE")
        if not snapshot.broker_ready:
            return RiskDecision(False, "RISK_BROKER_NOT_READY")
        try:
            quantity = float(request.quantity)
        except (TypeError, ValueError):
            return RiskDecision(False, "RISK_INVALID_QUANTITY")
        if quantity <= 0:
            return RiskDecision(False, "RISK_INVALID_QUANTITY")
        if quantity > self.limits.max_order_quantity:
            return RiskDecision(False, "RISK_MAX_ORDER_QUANTITY")
        projected_position = abs(float(snapshot.position_quantity)) + quantity
        if projected_position > self.limits.max_position_quantity + 1e-9:
            return RiskDecision(False, "RISK_MAX_POSITION_QUANTITY")
        if -float(snapshot.daily_pnl) >= self.limits.max_daily_loss:
            return RiskDecision(False, "RISK_DAILY_LOSS_LIMIT")
        if float(snapshot.projected_trade_loss) > self.limits.max_trade_loss + 1e-9:
            return RiskDecision(False, "RISK_TRADE_LOSS_LIMIT")
        return RiskDecision(True, "RISK_OK")
