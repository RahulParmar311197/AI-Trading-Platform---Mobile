from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.broker_portfolio_snapshot import BrokerPortfolioSnapshot
from app.portfolio_risk_aggregation import OpenOrderRiskInput, PositionRiskInput


@dataclass(frozen=True)
class SnapshotRiskInputs:
    positions: tuple[PositionRiskInput, ...]
    open_orders: tuple[OpenOrderRiskInput, ...]
    available: bool
    reason: str
    captured_at: datetime


class BrokerSnapshotRiskAdapter:
    """Convert the canonical broker snapshot into fail-closed risk inputs."""

    def adapt(self, snapshot: BrokerPortfolioSnapshot) -> SnapshotRiskInputs:
        if not snapshot.data_complete:
            return SnapshotRiskInputs((), (), False, snapshot.error or "broker snapshot incomplete", snapshot.captured_at)
        if snapshot.captured_at.tzinfo is None:
            return SnapshotRiskInputs((), (), False, "broker snapshot timestamp must be timezone-aware", snapshot.captured_at)
        age = datetime.now(timezone.utc) - snapshot.captured_at.astimezone(timezone.utc)
        if age.total_seconds() < 0:
            return SnapshotRiskInputs((), (), False, "broker snapshot timestamp is in the future", snapshot.captured_at)
        positions = tuple(PositionRiskInput(p.symbol, p.quantity, p.entry_price, p.stop_price, p.multiplier) for p in snapshot.positions)
        orders = tuple(OpenOrderRiskInput(o.symbol, o.quantity, o.entry_price, o.stop_price, o.multiplier) for o in snapshot.open_orders)
        return SnapshotRiskInputs(positions, orders, True, "broker snapshot accepted", snapshot.captured_at)
