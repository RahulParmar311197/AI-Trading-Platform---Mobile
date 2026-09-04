from __future__ import annotations

from dataclasses import dataclass
import math

from app.execution import ExecutionResult
from app.order_intent import OrderIntent
from app.trailing_stop import TrailingPolicy, update_stop


@dataclass
class Position:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    initial_stop: float | None = None
    entry_cost: float = 0.0
    realized_pnl: float = 0.0
    partial_taken: bool = False

    def __post_init__(self):
        self.symbol = str(self.symbol).strip().upper()
        self.side = str(self.side).strip().upper()
        if not self.symbol or self.side not in {"BUY", "SELL"}:
            raise ValueError("position symbol and side are required")
        for name in ("quantity", "entry_price", "stop_loss", "take_profit", "entry_cost", "realized_pnl"):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"position {name} must be finite")
        if self.quantity <= 0 or self.entry_price <= 0 or self.stop_loss <= 0 or self.take_profit <= 0:
            raise ValueError("position quantity and prices must be positive")
        if self.entry_cost < 0:
            raise ValueError("position entry_cost cannot be negative")
        if self.initial_stop is None:
            self.initial_stop = self.stop_loss
        if not math.isfinite(float(self.initial_stop)) or self.initial_stop <= 0:
            raise ValueError("position initial_stop must be positive and finite")

    def unrealized_pnl(self, mark_price: float, quantity: float | None = None) -> float:
        mark = float(mark_price)
        q = self.quantity if quantity is None else float(quantity)
        if not math.isfinite(mark) or mark <= 0 or not math.isfinite(q) or q <= 0 or q > self.quantity:
            raise ValueError("invalid mark price or quantity")
        direction = 1.0 if self.side == "BUY" else -1.0
        return (mark - self.entry_price) * q * direction


@dataclass(frozen=True)
class CloseResult:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    realized_pnl: float
    reason: str
    commission: float = 0.0
    slippage: float = 0.0


class PaperPortfolio:
    def __init__(self, initial_equity: float):
        initial = float(initial_equity)
        if not math.isfinite(initial) or initial <= 0:
            raise ValueError("initial_equity must be positive and finite")
        self.initial_equity = initial
        self.realized_pnl = 0.0
        self.positions: dict[str, Position] = {}
        self.total_commission = 0.0
        self.total_slippage = 0.0
        self.entry_commission = 0.0

    @property
    def equity(self):
        return self.initial_equity + self.realized_pnl - self.entry_commission

    @property
    def exposure(self):
        return sum(abs(p.entry_price * p.quantity) for p in self.positions.values())

    def apply_fill(self, order: OrderIntent, fill: ExecutionResult) -> Position:
        if order.symbol.strip().upper() in self.positions:
            raise RuntimeError("cannot overwrite an existing paper position for the same symbol")
        if order.side not in {"BUY", "SELL"}:
            raise ValueError("invalid order side")
        for name, value in (("fill quantity", fill.filled_quantity), ("fill price", fill.fill_price), ("commission", fill.commission), ("slippage", fill.slippage)):
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if fill.filled_quantity <= 0 or fill.fill_price <= 0 or fill.commission < 0 or fill.slippage < 0:
            raise ValueError("invalid fill")
        pos = Position(order.symbol, order.side, fill.filled_quantity, fill.fill_price, order.stop_loss, order.take_profit, order.stop_loss, fill.commission)
        self.total_commission += fill.commission
        self.total_slippage += fill.slippage
        self.entry_commission += fill.commission
        self.positions[pos.symbol] = pos
        return pos

    def update_trailing(self, prices: dict[str, float], policy: TrailingPolicy | None = None) -> None:
        for symbol, p in self.positions.items():
            if symbol in prices:
                price = float(prices[symbol])
                if not math.isfinite(price) or price <= 0:
                    raise ValueError(f"invalid trailing price for {symbol}")
                p.stop_loss = update_stop(p.side, p.entry_price, p.initial_stop, price, p.stop_loss, policy)

    def close_position(self, symbol: str, exit_price: float, reason: str = "MANUAL", quantity: float | None = None, commission: float = 0.0, slippage: float = 0.0) -> CloseResult:
        key = str(symbol).strip().upper()
        if key not in self.positions:
            raise KeyError(f"no open position: {symbol}")
        p = self.positions[key]
        q = p.quantity if quantity is None else float(quantity)
        px = float(exit_price)
        commission = float(commission)
        slippage = float(slippage)
        if not math.isfinite(px) or not math.isfinite(q) or not math.isfinite(commission) or not math.isfinite(slippage):
            raise ValueError("close values must be finite")
        if px <= 0 or q <= 0 or q > p.quantity or commission < 0 or slippage < 0:
            raise ValueError("invalid close")
        pnl = p.unrealized_pnl(px, q) - commission
        p.quantity -= q
        p.realized_pnl += pnl
        self.realized_pnl += pnl
        self.total_commission += commission
        self.total_slippage += slippage
        if p.quantity == 0:
            self.positions.pop(key)
        return CloseResult(key, p.side, p.entry_price, px, q, pnl, reason, commission, slippage)

    def partial_close(self, symbol: str, exit_price: float, quantity: float, move_stop_to_breakeven: bool = True, commission: float = 0.0, slippage: float = 0.0) -> CloseResult:
        result = self.close_position(symbol, exit_price, "PARTIAL_TP", quantity, commission, slippage)
        key = str(symbol).strip().upper()
        if key in self.positions and move_stop_to_breakeven:
            self.positions[key].stop_loss = self.positions[key].entry_price
        if key in self.positions:
            self.positions[key].partial_taken = True
        return result

    def process_ohlc_bar(self, bars: dict[str, object]) -> list[CloseResult]:
        closed = []
        for symbol, p in list(self.positions.items()):
            bar = bars.get(symbol)
            if bar is None:
                continue
            try:
                high = float(bar.high)
                low = float(bar.low)
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid OHLC bar for {symbol}") from exc
            if not math.isfinite(high) or not math.isfinite(low) or high <= 0 or low <= 0 or high < low:
                raise ValueError(f"invalid OHLC range for {symbol}")
            reason = None
            exit_price = None
            if p.side == "BUY":
                if low <= p.stop_loss:
                    reason, exit_price = "STOP_LOSS", p.stop_loss
                elif high >= p.take_profit:
                    reason, exit_price = "TAKE_PROFIT", p.take_profit
            else:
                if high >= p.stop_loss:
                    reason, exit_price = "STOP_LOSS", p.stop_loss
                elif low <= p.take_profit:
                    reason, exit_price = "TAKE_PROFIT", p.take_profit
            if reason:
                closed.append(self.close_position(symbol, exit_price, reason))
        return closed

    def process_bar(self, prices: dict[str, float]) -> list[CloseResult]:
        closed = []
        for symbol, p in list(self.positions.items()):
            if symbol not in prices:
                continue
            px = float(prices[symbol])
            if not math.isfinite(px) or px <= 0:
                raise ValueError(f"invalid price for {symbol}")
            reason = None
            if p.side == "BUY":
                if px <= p.stop_loss:
                    reason = "STOP_LOSS"
                elif px >= p.take_profit:
                    reason = "TAKE_PROFIT"
            else:
                if px >= p.stop_loss:
                    reason = "STOP_LOSS"
                elif px <= p.take_profit:
                    reason = "TAKE_PROFIT"
            if reason:
                closed.append(self.close_position(symbol, px, reason))
        return closed

    def mark(self, prices: dict[str, float]) -> dict:
        missing = [symbol for symbol in self.positions if symbol not in prices]
        if missing:
            raise ValueError(f"incomplete portfolio valuation; missing prices for: {', '.join(sorted(missing))}")
        unrealized = 0.0
        for p in self.positions.values():
            unrealized += p.unrealized_pnl(float(prices[p.symbol]))
        return {
            "initial_equity": self.initial_equity,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": unrealized,
            "equity": self.equity + unrealized,
            "exposure": self.exposure,
            "open_positions": len(self.positions),
            "total_commission": self.total_commission,
            "total_slippage": self.total_slippage,
        }
