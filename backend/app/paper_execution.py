from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class PaperPosition:
    id: str
    symbol: str
    side: str
    quantity: float
    entry: float
    stop_loss: float
    target: float
    opened_at: str
    status: str = "OPEN"
    exit: float | None = None
    realized_pnl: float = 0.0


class PaperBroker:
    def __init__(self):
        self.positions: dict[str, PaperPosition] = {}

    def open(self, symbol: str, side: str, quantity: float, entry: float, stop_loss: float, target: float) -> PaperPosition:
        if quantity <= 0 or entry <= 0:
            raise ValueError("quantity and entry must be positive")
        position = PaperPosition(str(uuid4()), symbol.upper(), side, quantity, entry, stop_loss, target, datetime.now(timezone.utc).isoformat())
        self.positions[position.id] = position
        return position

    def close(self, position_id: str, exit_price: float) -> PaperPosition:
        position = self.positions.get(position_id)
        if not position or position.status != "OPEN":
            raise ValueError("open paper position not found")
        position.exit = exit_price
        position.status = "CLOSED"
        direction = 1 if position.side == "BUY" else -1
        position.realized_pnl = (exit_price - position.entry) * position.quantity * direction
        return position

    def mark(self, position_id: str, price: float) -> dict:
        position = self.positions.get(position_id)
        if not position:
            raise ValueError("position not found")
        direction = 1 if position.side == "BUY" else -1
        unrealized = (price - position.entry) * position.quantity * direction
        return {"position_id": position.id, "status": position.status, "price": price, "unrealized_pnl": unrealized}

    def list(self):
        return list(self.positions.values())


paper_broker = PaperBroker()
