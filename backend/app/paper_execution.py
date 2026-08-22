from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.risk_engine import RiskLimits, evaluate
from app.trade_journal import JournalTrade, journal, now_iso


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
        self.daily_pnl = 0.0

    def open(self, symbol: str, side: str, quantity: float, entry: float, stop_loss: float, target: float,
             equity: float | None = None, max_risk_percent: float = 1.0, max_daily_loss_percent: float = 3.0,
             max_exposure_percent: float = 20.0, max_positions: int = 5) -> PaperPosition:
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if quantity <= 0 or entry <= 0 or stop_loss <= 0 or target <= 0:
            raise ValueError("quantity and prices must be positive")
        if equity is not None:
            proposed_risk = abs(entry - stop_loss) * quantity
            proposed_exposure = entry * quantity
            decision = evaluate(
                equity=equity, daily_pnl=self.daily_pnl, proposed_risk=proposed_risk,
                proposed_exposure=proposed_exposure, open_positions=len(self.open_positions()),
                limits=RiskLimits(max_risk_percent, max_daily_loss_percent, max_exposure_percent, max_positions),
            )
            if not decision.allowed:
                raise ValueError("RISK_VETO: " + "; ".join(decision.reasons))
        position = PaperPosition(str(uuid4()), symbol.upper(), side, quantity, entry, stop_loss, target, datetime.now(timezone.utc).isoformat())
        self.positions[position.id] = position
        return position

    def close(self, position_id: str, exit_price: float, exit_reason: str = "MANUAL") -> PaperPosition:
        position = self.positions.get(position_id)
        if not position or position.status != "OPEN":
            raise ValueError("open paper position not found")
        if exit_price <= 0:
            raise ValueError("exit price must be positive")
        position.exit = exit_price
        position.status = "CLOSED"
        direction = 1 if position.side == "BUY" else -1
        position.realized_pnl = (exit_price - position.entry) * position.quantity * direction
        self.daily_pnl += position.realized_pnl
        journal.record(JournalTrade(
            id=position.id, symbol=position.symbol, side=position.side, entry=position.entry,
            exit=exit_price, quantity=position.quantity, pnl=position.realized_pnl,
            strategy="PAPER", opened_at=position.opened_at, closed_at=now_iso(), exit_reason=exit_reason,
        ))
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

    def open_positions(self):
        return [p for p in self.positions.values() if p.status == "OPEN"]


paper_broker = PaperBroker()
