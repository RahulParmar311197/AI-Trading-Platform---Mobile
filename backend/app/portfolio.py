from __future__ import annotations
from dataclasses import dataclass
from app.execution import ExecutionResult
from app.order_intent import OrderIntent

@dataclass
class Position:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    realized_pnl: float = 0.0

    def unrealized_pnl(self, mark_price: float) -> float:
        direction = 1.0 if self.side == 'BUY' else -1.0
        return (mark_price - self.entry_price) * self.quantity * direction

class PaperPortfolio:
    def __init__(self, initial_equity: float):
        if initial_equity <= 0: raise ValueError('initial_equity must be positive')
        self.initial_equity=initial_equity
        self.realized_pnl=0.0
        self.positions: dict[str, Position] = {}

    @property
    def equity(self) -> float: return self.initial_equity + self.realized_pnl

    @property
    def exposure(self) -> float: return sum(abs(p.entry_price*p.quantity) for p in self.positions.values())

    def apply_fill(self, order: OrderIntent, fill: ExecutionResult) -> Position:
        if fill.filled_quantity <= 0: raise ValueError('fill quantity must be positive')
        pos=Position(order.symbol,order.side,fill.filled_quantity,fill.fill_price,order.stop_loss,order.take_profit)
        self.positions[order.symbol]=pos
        return pos

    def mark(self, prices: dict[str,float]) -> dict:
        unrealized=sum(p.unrealized_pnl(prices[p.symbol]) for p in self.positions.values() if p.symbol in prices)
        return {'initial_equity':self.initial_equity,'realized_pnl':self.realized_pnl,'unrealized_pnl':unrealized,'equity':self.equity+unrealized,'exposure':self.exposure,'open_positions':len(self.positions)}
