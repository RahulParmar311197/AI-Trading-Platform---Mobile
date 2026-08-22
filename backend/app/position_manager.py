from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class Position:
    symbol: str
    side: str
    quantity: float
    avg_entry: float
    stop: float | None = None
    target: float | None = None
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    status: str = "OPEN"
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PositionManager:
    def __init__(self): self.positions: dict[str, Position] = {}
    def open(self, symbol, side, quantity, price, stop=None, target=None):
        if quantity <= 0 or price <= 0: raise ValueError("invalid position")
        key=symbol.upper()
        if key in self.positions and self.positions[key].status == "OPEN": raise ValueError("position already open")
        p=Position(key,side.upper(),quantity,price,stop,target); self.positions[key]=p; return p
    def mark(self, symbol, price):
        p=self.positions[symbol.upper()]; direction=1 if p.side=="BUY" else -1
        p.unrealized_pnl=(price-p.avg_entry)*p.quantity*direction; p.updated_at=datetime.now(timezone.utc).isoformat(); return p
    def partial_exit(self, symbol, quantity, price):
        p=self.positions[symbol.upper()]
        if quantity <= 0 or quantity > p.quantity: raise ValueError("invalid exit quantity")
        direction=1 if p.side=="BUY" else -1; p.realized_pnl += (price-p.avg_entry)*quantity*direction; p.quantity -= quantity
        if p.quantity == 0: p.status="CLOSED"; p.unrealized_pnl=0.0
        p.updated_at=datetime.now(timezone.utc).isoformat(); return p
    def reconcile(self, broker_positions: list[dict]):
        broker={str(x["symbol"]).upper(): x for x in broker_positions}; drift=[]
        for symbol,p in self.positions.items():
            b=broker.get(symbol); broker_qty=float(b.get("quantity",0)) if b else 0.0
            if not b or broker_qty != p.quantity: drift.append({"symbol":symbol,"internal_quantity":p.quantity,"broker_quantity":broker_qty})
        return {"ok":not drift,"drift":drift}
