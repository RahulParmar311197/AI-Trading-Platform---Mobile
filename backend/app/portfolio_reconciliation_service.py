from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class PositionMismatch:
    symbol: str
    local_quantity: float
    broker_quantity: float


@dataclass(frozen=True)
class PortfolioReconciliationResult:
    """Position comparison result; not sufficient for execution authorization."""

    matched: bool
    mismatches: tuple[PositionMismatch, ...]
    errors: tuple[str, ...] = ()


# Backward-compatible alias for existing callers. New code should use the explicit name.
ReconciliationResult = PortfolioReconciliationResult


def _signed_quantity(position: dict) -> float:
    if "signed_quantity" in position:
        return float(position["signed_quantity"])
    quantity_value = position.get("quantity", position.get("net_quantity", position.get("netQty")))
    if quantity_value is None:
        raise ValueError("position quantity missing")
    quantity = float(quantity_value)
    if quantity != quantity or quantity in (float("inf"), float("-inf")):
        raise ValueError("position quantity is not finite")
    side = str(position.get("side", "")).strip().upper()
    if side in {"SELL", "SHORT", "S", "-1"}:
        return -abs(quantity)
    if side in {"BUY", "LONG", "B", "1"}:
        return abs(quantity)
    if side:
        raise ValueError(f"unsupported position side: {side}")
    return quantity


class PortfolioReconciliationService:
    """Compare normalized broker/local positions and fail closed on bad remote data."""

    def compare(self, local_positions: Mapping[str, float], broker_positions: list[dict]) -> PortfolioReconciliationResult:
        remote: dict[str, float] = {}
        errors: list[str] = []
        for index, position in enumerate(broker_positions):
            if not isinstance(position, dict):
                errors.append(f"position[{index}]: payload is not an object")
                continue
            symbol = str(position.get("symbol", position.get("trading_symbol", ""))).strip().upper()
            if not symbol:
                errors.append(f"position[{index}]: symbol missing")
                continue
            try:
                quantity = _signed_quantity(position)
            except (TypeError, ValueError) as exc:
                errors.append(f"position[{index}] {symbol}: {exc}")
                continue
            remote[symbol] = remote.get(symbol, 0.0) + quantity
        local: dict[str, float] = {}
        for symbol, quantity in local_positions.items():
            key = str(symbol).strip().upper()
            if not key:
                continue
            try:
                value = float(quantity)
                if value != value or value in (float("inf"), float("-inf")):
                    errors.append(f"local {key}: quantity is not finite")
                    continue
                local[key] = value
            except (TypeError, ValueError):
                errors.append(f"local {key}: invalid quantity")
        symbols = set(local) | set(remote)
        mismatches = tuple(
            PositionMismatch(symbol=s, local_quantity=local.get(s, 0.0), broker_quantity=remote.get(s, 0.0))
            for s in sorted(symbols)
            if abs(local.get(s, 0.0) - remote.get(s, 0.0)) > 1e-9
        )
        return PortfolioReconciliationResult(matched=not mismatches and not errors, mismatches=mismatches, errors=tuple(errors))