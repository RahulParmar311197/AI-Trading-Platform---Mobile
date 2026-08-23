from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.paper_broker import PaperBroker, PaperOrder
from app.trade_plan import TradeAction


@dataclass(frozen=True)
class ClosedTrade:
    order_id: str
    symbol: str
    action: TradeAction
    entry: float
    exit: float
    quantity: int
    pnl: float
    reason: str
    closed_at: datetime


class PaperPortfolio:
    def __init__(self, initial_cash: float = 1_000_000.0, fee_per_order: float = 0.0, slippage_per_unit: float = 0.0):
        if initial_cash <= 0 or fee_per_order < 0 or slippage_per_unit < 0:
            raise ValueError("invalid portfolio configuration")
        self.broker = PaperBroker(initial_cash)
        self.initial_cash = initial_cash
        self.realized_pnl = 0.0
        self.fees = 0.0
        self.entry_fees = 0.0
        self.fee_per_order = fee_per_order
        self.slippage = slippage_per_unit
        self.closed: list[ClosedTrade] = []
        self.open_ids: set[str] = set()

    def open(self, plan) -> str:
        oid = self.broker.submit(plan)
        self.open_ids.add(oid)
        self.fees += self.fee_per_order
        self.entry_fees += self.fee_per_order
        return oid

    def _pnl(self, o: PaperOrder, price: float) -> float:
        return (price - o.entry) * o.quantity * (1 if o.action == TradeAction.BUY else -1)

    def update(self, prices: dict[str, float]) -> list[ClosedTrade]:
        newly: list[ClosedTrade] = []
        for oid in list(self.open_ids):
            o = self.broker.get_order(oid)
            price = prices.get(o.symbol) if o else None
            if not o or price is None:
                continue
            reason = None
            exit_price = price
            if o.action == TradeAction.BUY:
                if price <= o.stop_loss:
                    reason = "STOP_LOSS"
                    exit_price = o.stop_loss - self.slippage
                elif price >= o.take_profit:
                    reason = "TAKE_PROFIT"
                    exit_price = o.take_profit - self.slippage
            else:
                if price >= o.stop_loss:
                    reason = "STOP_LOSS"
                    exit_price = o.stop_loss + self.slippage
                elif price <= o.take_profit:
                    reason = "TAKE_PROFIT"
                    exit_price = o.take_profit + self.slippage
            if reason:
                pnl = self._pnl(o, exit_price) - self.fee_per_order
                self.realized_pnl += pnl
                self.fees += self.fee_per_order
                trade = ClosedTrade(oid, o.symbol, o.action, o.entry, exit_price, o.quantity, pnl, reason, datetime.now(timezone.utc))
                self.closed.append(trade)
                self.open_ids.remove(oid)
                newly.append(trade)
        return newly

    def unrealized_pnl(self, prices: dict[str, float]) -> float:
        total = 0.0
        for oid in self.open_ids:
            o = self.broker.get_order(oid)
            if o and o.symbol in prices:
                total += self._pnl(o, prices[o.symbol])
        return total

    def equity(self, prices: dict[str, float]) -> float:
        # realized_pnl already includes close fees; entry fees are tracked
        # separately so they are not charged twice.
        return self.initial_cash + self.realized_pnl + self.unrealized_pnl(prices) - self.entry_fees
