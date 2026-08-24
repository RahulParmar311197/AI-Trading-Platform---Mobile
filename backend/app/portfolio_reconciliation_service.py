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


class PortfolioReconciliationService:
    """Compare broker and local positions and fail closed on exposure mismatch."""

    def compare(self, local_positions: Mapping[str, float], broker_positions: list[dict]) -> ReconciliationResult:
        remote = {str(p.get("symbol", "")).upper(): float(p.get("quantity", 0) or 0) for p in broker_positions if p.get("symbol")}
        symbols = set(local_positions) | set(remote)
        mismatches = tuple(
            PositionMismatch(symbol=s, local_quantity=float(local_positions.get(s, 0)), broker_quantity=remote.get(s, 0.0))
            for s in sorted(symbols)
            if float(local_positions.get(s, 0)) != remote.get(s, 0.0)
        )
        return ReconciliationResult(matched=not mismatches, mismatches=mismatches)
