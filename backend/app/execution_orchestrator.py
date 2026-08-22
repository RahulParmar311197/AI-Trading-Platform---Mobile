from __future__ import annotations
from dataclasses import dataclass
from app.order_intent import OrderIntent
from app.risk_gateway import authorize, RiskGatewayResult
from app.order_lifecycle import OrderLifecycle, OrderStatus

@dataclass(frozen=True)
class ExecutionResult:
    accepted: bool
    reason: str
    risk: RiskGatewayResult | None

class ExecutionOrchestrator:
    def __init__(self, lifecycle: OrderLifecycle):
        self.lifecycle = lifecycle

    def submit_signal(self, *, order: OrderIntent, equity: float, daily_pnl: float, open_positions: int, recent_losses: int = 0) -> ExecutionResult:
        risk = authorize(order=order, equity=equity, daily_pnl=daily_pnl, open_positions=open_positions, recent_losses=recent_losses)
        if not risk.approved:
            return ExecutionResult(False, 'RISK_REJECTED', risk)
        if order.symbol in self.lifecycle.positions and self.lifecycle.positions[order.symbol].side == order.side:
            return ExecutionResult(False, 'SAME_SIDE_POSITION_ALREADY_OPEN', risk)
        self.lifecycle.create(order.symbol + '-' + str(len(self.lifecycle.orders) + 1), order.symbol, order.side, order.quantity)
        return ExecutionResult(True, 'ORDER_ACCEPTED', risk)
