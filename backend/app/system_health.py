from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock


@dataclass(frozen=True)
class HealthCheck:
    name: str
    healthy: bool
    message: str = ""
    checked_at: datetime | None = None


@dataclass
class SystemHealth:
    checks: dict[str, HealthCheck] = field(default_factory=dict)
    updated_at: datetime | None = None


class TradingSystemHealth:
    """Tracks critical trading dependencies and exposes liveness/readiness state."""

    def __init__(self, stale_after_seconds: float = 30.0):
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        self.stale_after_seconds = stale_after_seconds
        self.state = SystemHealth()
        self._lock = Lock()

    def record(self, name: str, healthy: bool, message: str = "") -> HealthCheck:
        check = HealthCheck(name, healthy, message, datetime.now(timezone.utc))
        with self._lock:
            self.state.checks[name] = check
            self.state.updated_at = check.checked_at
        return check

    def heartbeat(self, name: str, timestamp: datetime | None = None) -> HealthCheck:
        ts = timestamp or datetime.now(timezone.utc)
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return self.record(name, age <= self.stale_after_seconds, f"age_seconds={age:.3f}")

    def liveness(self) -> bool:
        return True

    def readiness(self) -> bool:
        with self._lock:
            return bool(self.state.checks) and all(c.healthy for c in self.state.checks.values())

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "ready": self.readiness(),
                "updated_at": self.state.updated_at.isoformat() if self.state.updated_at else None,
                "checks": {
                    name: {"healthy": c.healthy, "message": c.message, "checked_at": c.checked_at.isoformat() if c.checked_at else None}
                    for name, c in self.state.checks.items()
                },
            }
