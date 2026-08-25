from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.broker_portfolio_snapshot import BrokerPortfolioSnapshot


@dataclass(frozen=True)
class SnapshotFreshnessResult:
    fresh: bool
    age_seconds: float
    reason: str


class BrokerSnapshotFreshnessPolicy:
    """Fail-closed freshness policy for broker portfolio snapshots."""

    def __init__(self, max_age_seconds: float = 5.0) -> None:
        if max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")
        self.max_age_seconds = float(max_age_seconds)

    def evaluate(self, snapshot: BrokerPortfolioSnapshot, now: datetime | None = None) -> SnapshotFreshnessResult:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if snapshot.captured_at.tzinfo is None:
            return SnapshotFreshnessResult(False, float("inf"), "snapshot timestamp must be timezone-aware")
        age = (current.astimezone(timezone.utc) - snapshot.captured_at.astimezone(timezone.utc)).total_seconds()
        if age < 0:
            return SnapshotFreshnessResult(False, age, "broker snapshot timestamp is in the future")
        if age > self.max_age_seconds:
            return SnapshotFreshnessResult(False, age, f"broker snapshot stale: age {age:.3f}s exceeds {self.max_age_seconds:.3f}s")
        return SnapshotFreshnessResult(True, age, "broker snapshot is fresh")
