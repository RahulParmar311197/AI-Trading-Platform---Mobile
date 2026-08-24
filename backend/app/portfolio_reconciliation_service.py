from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class PositionMismatch:
    symbol: str
    local_quantity: float
    broker_quantity: float


@dataclass(frozen=True)
class ReconciliationResult:
    matched: bool
    mismatches: tuple[PositionMismatch, ...]


def _signed_quantity(position: dict) -> float:
    if "signed_quantity" in position:
        return float(position.get("signed_quantity") or 0)
    quantity = float(position.get("quantity", position.get("net_quantity", position.get("netQty", 0))) or 0)
    side = str(position.get("side", "")).strip().upper()
    if side in {"SELL", "SHORT", "S", "-1"}:
        return -abs(quantity)
    if side in {"BUY", "LONG", "B", "1"}:
        return abs(quantity)
    return quantity


class PortfolioReconciliationService:
    """Compare normalized broker and local positions and fail closed on exposure mismatch."""

    def compare(self, local_positions: Mapping[str, float], broker_positions: list[dict]) -> ReconciliationResult:
        remote: dict[str, float] = {}
        for position in broker_positions:
            symbol = str(position.get("symbol", position.get("trading_symbol", ""))).strip().upper()
            if not symbol:
                continue
            remote[symbol] = remote.get(symbol, 0.0) + _signed_quantity(position)
        local = {str(symbol).strip().upper(): float(quantity) for symbol, quantity in local_positions.items() if str(symbol).strip()}
        symbols = set(local) | set(remote)
        mismatches = tuple(
            PositionMismatch(symbol=s, local_quantity=local.get(s, 0.0), broker_quantity=remote.get(s, 0.0))
            for s in sorted(symbols)
            if abs(local.get(s, 0.0) - remote.get(s, 0.0)) > 1e-9
        )
        return ReconciliationResult(matched=not mismatches, mismatches=mismatches)
