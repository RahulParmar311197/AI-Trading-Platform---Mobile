from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.order_intent import OrderIntent
from app.order_lifecycle import OrderLifecycle
from app.risk_gateway import RiskGatewayResult, authorize
from app.trade_plan import TradeAction, TradePlan


@dataclass(frozen=True)
class ExecutionResult:
    accepted: bool
    reason: str
    risk: RiskGatewayResult | None = None
    order_id: str | None = None


class BrokerAdapter:
    """Legacy compatibility interface; live adapters must use the central execution service."""
    def submit(self, plan: TradePlan) -> str:
        raise NotImplementedError


class ExecutionOrchestrator:
    """Compatibility facade for legacy callers.

    This class intentionally no longer submits directly to a BrokerAdapter. The
    production execution path is OrderExecutionService -> ExecutionAuthorization
    -> BrokerRouter. Keeping the old API as a rejecting facade prevents an older
    caller from silently bypassing startup, safety, risk and idempotency gates.
    """

    def __init__(self, lifecycle: OrderLifecycle | None = None, broker: BrokerAdapter | None = None, live_enabled: bool = False):
        self.lifecycle = lifecycle
        self.broker = broker
        self.live_enabled = live_enabled

    def submit_signal(self, *, order: OrderIntent, equity: float, daily_pnl: float, open_positions: int, recent_losses: int = 0) -> ExecutionResult:
        if self.lifecycle is None:
            return ExecutionResult(False, "ORDER_LIFECYCLE_NOT_CONFIGURED")
        risk = authorize(order=order, equity=equity, daily_pnl=daily_pnl, open_positions=open_positions, recent_losses=recent_losses)
        if not risk.approved:
            return ExecutionResult(False, "RISK_REJECTED", risk=risk)
        existing = self.lifecycle.positions.get(order.symbol)
        if existing is not None and existing.side == order.side:
            return ExecutionResult(False, "SAME_SIDE_POSITION_ALREADY_OPEN", risk=risk)
        order_id = f"{order.symbol}-{len(self.lifecycle.orders) + 1}"
        self.lifecycle.create(order_id, order.symbol, order.side, order.quantity)
        return ExecutionResult(True, "ORDER_ACCEPTED", risk=risk, order_id=order_id)

    def submit(self, plan: TradePlan, kill_switch_armed: bool = False) -> ExecutionResult:
        if not self.live_enabled:
            return ExecutionResult(False, "LIVE_EXECUTION_DISABLED")
        if not kill_switch_armed:
            return ExecutionResult(False, "KILL_SWITCH_BLOCKED")
        if plan.expires_at <= datetime.now(timezone.utc):
            return ExecutionResult(False, "TRADE_PLAN_EXPIRED")
        if plan.quantity < 1:
            return ExecutionResult(False, "INVALID_QUANTITY")
        if plan.action not in (TradeAction.BUY, TradeAction.SELL):
            return ExecutionResult(False, "INVALID_ACTION")
        if self.broker is None:
            return ExecutionResult(False, "BROKER_NOT_CONFIGURED")
        return ExecutionResult(False, "LEGACY_DIRECT_BROKER_EXECUTION_DISABLED")
