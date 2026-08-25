from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.operational_metrics import TradingMetricsCollector
from app.trading_observability import TradingAuditLogger


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
    """Tracks positions, exits, P&L and broker reconciliation with telemetry."""

    def __init__(self, metrics: TradingMetricsCollector | None = None, audit: TradingAuditLogger | None = None):
        self.positions: dict[str, Position] = {}
        self.metrics = metrics or TradingMetricsCollector()
        self.audit = audit or TradingAuditLogger()

    def open(self, symbol, side, quantity, price, stop=None, target=None):
        if quantity <= 0 or price <= 0:
            raise ValueError("invalid position")
        key = symbol.upper(); direction = side.upper()
        if direction not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if (stop is not None and stop <= 0) or (target is not None and target <= 0):
            raise ValueError("stop/target must be positive")
        if direction == "BUY" and stop is not None and stop >= price:
            raise ValueError("long stop must be below entry")
        if direction == "BUY" and target is not None and target <= price:
            raise ValueError("long target must be above entry")
        if direction == "SELL" and stop is not None and stop <= price:
            raise ValueError("short stop must be above entry")
        if direction == "SELL" and target is not None and target >= price:
            raise ValueError("short target must be below entry")
        if key in self.positions and self.positions[key].status == "OPEN":
            raise ValueError("position already open")
        p = Position(key, direction, quantity, price, stop, target)
        self.positions[key] = p
        self.audit.emit("POSITION_OPENED", symbol=key, data={"side": direction, "quantity": quantity, "entry": price})
        return p

    def mark(self, symbol, price):
        if price <= 0: raise ValueError("price must be positive")
        p = self.positions[symbol.upper()]
        direction = 1 if p.side == "BUY" else -1
        p.unrealized_pnl = (price - p.avg_entry) * p.quantity * direction
        p.updated_at = datetime.now(timezone.utc).isoformat()
        return p

    def check_exit(self, symbol, high, low):
        p = self.positions.get(symbol.upper())
        if not p or p.status != "OPEN": return None
        if p.side == "BUY":
            if p.stop is not None and low <= p.stop: return "STOP_LOSS"
            if p.target is not None and high >= p.target: return "TAKE_PROFIT"
        else:
            if p.stop is not None and high >= p.stop: return "STOP_LOSS"
            if p.target is not None and low <= p.target: return "TAKE_PROFIT"
        return None

    def partial_exit(self, symbol, quantity, price):
        key = symbol.upper(); p = self.positions[key]
        if p.status != "OPEN" or quantity <= 0 or quantity > p.quantity or price <= 0:
            raise ValueError("invalid exit")
        direction = 1 if p.side == "BUY" else -1
        pnl = (price - p.avg_entry) * quantity * direction
        p.realized_pnl += pnl
        p.quantity -= quantity
        if p.quantity == 0:
            p.status = "CLOSED"; p.unrealized_pnl = 0.0
            self.audit.emit("POSITION_CLOSED", symbol=key, data={"reason": "EXIT", "price": price, "pnl": pnl})
        else:
            self.audit.emit("PARTIAL_EXIT", symbol=key, data={"quantity": quantity, "price": price, "pnl": pnl})
        self.metrics.record_pnl(pnl)
        self.metrics.increment("orders_filled")
        p.updated_at = datetime.now(timezone.utc).isoformat()
        return p

    def reconcile(self, broker_positions: list[dict]):
        broker: dict[str, float] = {}
        for item in broker_positions:
            symbol = str(item.get("symbol", "")).strip().upper()
            if not symbol: raise ValueError("broker position missing symbol")
            if symbol in broker: raise ValueError(f"duplicate broker position: {symbol}")
            raw_quantity = float(item.get("quantity", 0))
            if raw_quantity != raw_quantity or raw_quantity in (float("inf"), float("-inf")):
                raise ValueError(f"invalid broker position quantity: {symbol}")
            broker[symbol] = raw_quantity
        drift = []
        internal_symbols: set[str] = set()
        for symbol, position in self.positions.items():
            if position.status != "OPEN": continue
            internal_symbols.add(symbol)
            internal_qty = (1.0 if position.side == "BUY" else -1.0) * position.quantity
            broker_qty = broker.get(symbol, 0.0)
            if broker_qty != internal_qty:
                drift.append({"symbol": symbol, "internal_quantity": internal_qty, "broker_quantity": broker_qty})
        for symbol, broker_qty in broker.items():
            if symbol not in internal_symbols and broker_qty != 0:
                drift.append({"symbol": symbol, "internal_quantity": 0.0, "broker_quantity": broker_qty})
        if drift:
            self.metrics.increment("reconciliation_failures")
            self.audit.emit("POSITION_RECONCILIATION_DRIFT", severity="ERROR", data={"drift": drift})
        else:
            self.audit.emit("POSITION_RECONCILIATION_OK")
        return {"ok": not drift, "drift": drift}
