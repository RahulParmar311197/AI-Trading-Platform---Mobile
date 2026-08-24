from dataclasses import dataclass, field
from typing import Any


def _mtm_pnl(quantity: float, average_price: float, last_price: float) -> float:
    if quantity >= 0:
        return (last_price - average_price) * quantity
    return (average_price - last_price) * abs(quantity)


@dataclass
class NormalizedPosition:
    symbol: str
    quantity: float = 0.0
    average_price: float = 0.0
    last_price: float = 0.0
    pnl: float = 0.0
    side: str = "LONG"
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def gross_exposure(self) -> float:
        return abs(self.quantity * self.last_price)

    @property
    def calculated_unrealized_pnl(self) -> float:
        return _mtm_pnl(self.quantity, self.average_price, self.last_price)


@dataclass
class NormalizedHolding:
    symbol: str
    quantity: float = 0.0
    average_price: float = 0.0
    last_price: float = 0.0
    pnl: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def gross_exposure(self) -> float:
        return abs(self.quantity * self.last_price)

    @property
    def calculated_unrealized_pnl(self) -> float:
        return _mtm_pnl(self.quantity, self.average_price, self.last_price)


@dataclass
class PortfolioState:
    broker: str
    account_id: int
    profile: dict[str, Any] = field(default_factory=dict)
    positions: list[NormalizedPosition] = field(default_factory=list)
    holdings: list[NormalizedHolding] = field(default_factory=list)
    fetched_at: str | None = None

    @property
    def net_exposure(self) -> float:
        return sum(p.quantity * p.last_price for p in self.positions)

    @property
    def gross_exposure(self) -> float:
        return sum(p.gross_exposure for p in self.positions) + sum(h.gross_exposure for h in self.holdings)

    @property
    def unrealized_pnl(self) -> float:
        return sum(p.pnl for p in self.positions) + sum(h.pnl for h in self.holdings)

    @property
    def calculated_unrealized_pnl(self) -> float:
        return sum(p.calculated_unrealized_pnl for p in self.positions) + sum(h.calculated_unrealized_pnl for h in self.holdings)


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list): return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        data = payload.get("data", payload.get("results", []))
        if isinstance(data, list): return [x for x in data if isinstance(x, dict)]
    return []


def normalize_portfolio(account_id: int, profile: Any, positions: Any, holdings: Any) -> PortfolioState:
    ps=[]
    for r in _rows(positions):
        qty=float(r.get("quantity", r.get("qty", 0)) or 0)
        ps.append(NormalizedPosition(symbol=str(r.get("trading_symbol", r.get("symbol", r.get("instrument_token", "")))), quantity=qty, average_price=float(r.get("average_price", 0) or 0), last_price=float(r.get("last_price", r.get("ltp", 0)) or 0), pnl=float(r.get("pnl", r.get("unrealised", 0)) or 0), side="SHORT" if qty < 0 else "LONG", raw=r))
    hs=[]
    for r in _rows(holdings):
        hs.append(NormalizedHolding(symbol=str(r.get("trading_symbol", r.get("symbol", r.get("instrument_token", "")))), quantity=float(r.get("quantity", r.get("qty", 0)) or 0), average_price=float(r.get("average_price", 0) or 0), last_price=float(r.get("last_price", r.get("ltp", 0)) or 0), pnl=float(r.get("pnl", r.get("unrealised", 0)) or 0), raw=r))
    return PortfolioState(broker="upstox", account_id=account_id, profile=profile if isinstance(profile, dict) else {}, positions=ps, holdings=hs)
