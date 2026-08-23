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
    def submit(self, plan: TradePlan) -> str:
        raise NotImplementedError


class ExecutionOrchestrator:
    def __init__(
        self,
        lifecycle: OrderLifecycle | None = None,
        broker: BrokerAdapter | None = None,
        live_enabled: bool = False,
    ):
        self.lifecycle = lifecycle
        self.broker = broker
        self.live_enabled = live_enabled

    def submit_signal(
        self,
        *,
        order: OrderIntent,
        equity: float,
        daily_pnl: float,
        open_positions: int,
        recent_losses: int = 0,
    ) -> ExecutionResult:
        if self.lifecycle is None:
            return ExecutionResult(
                accepted=False,
                reason="ORDER_LIFECYCLE_NOT_CONFIGURED",
            )

        risk = authorize(
            order=order,
            equity=equity,
            daily_pnl=daily_pnl,
            open_positions=open_positions,
            recent_losses=recent_losses,
        )

        if not risk.approved:
            return ExecutionResult(
                accepted=False,
                reason="RISK_REJECTED",
                risk=risk,
            )

        existing = self.lifecycle.positions.get(order.symbol)

        if existing is not None and existing.side == order.side:
            return ExecutionResult(
                accepted=False,
                reason="SAME_SIDE_POSITION_ALREADY_OPEN",
                risk=risk,
            )

        order_id = (
            f"{order.symbol}-"
            f"{len(self.lifecycle.orders) + 1}"
        )

        self.lifecycle.create(
            order_id,
            order.symbol,
            order.side,
            order.quantity,
        )

        return ExecutionResult(
            accepted=True,
            reason="ORDER_ACCEPTED",
            risk=risk,
            order_id=order_id,
        )

    def submit(
        self,
        plan: TradePlan,
        kill_switch_armed: bool = False,
    ) -> ExecutionResult:
        if not self.live_enabled:
            return ExecutionResult(
                accepted=False,
                reason="LIVE_EXECUTION_DISABLED",
            )

        if not kill_switch_armed:
            return ExecutionResult(
                accepted=False,
                reason="KILL_SWITCH_BLOCKED",
            )

        if plan.expires_at <= datetime.now(timezone.utc):
            return ExecutionResult(
                accepted=False,
                reason="TRADE_PLAN_EXPIRED",
            )

        if plan.quantity < 1:
            return ExecutionResult(
                accepted=False,
                reason="INVALID_QUANTITY",
            )

        if plan.action not in (
            TradeAction.BUY,
            TradeAction.SELL,
        ):
            return ExecutionResult(
                accepted=False,
                reason="INVALID_ACTION",
            )

        if self.broker is None:
            return ExecutionResult(
                accepted=False,
                reason="BROKER_NOT_CONFIGURED",
            )

        try:
            order_id = self.broker.submit(plan)
        except Exception as exc:
            return ExecutionResult(
                accepted=False,
                reason=f"BROKER_REJECTED: {exc}",
            )

        return ExecutionResult(
            accepted=True,
            reason="ORDER_SUBMITTED",
            order_id=order_id,
        )