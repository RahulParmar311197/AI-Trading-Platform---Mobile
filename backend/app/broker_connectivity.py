from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import time


class ConnectivityState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"
    RECOVERING = "RECOVERING"


BrokerConnectionState = ConnectivityState


@dataclass(frozen=True)
class ConnectivitySnapshot:
    state: ConnectivityState
    failures: int
    last_success_at: float | None
    next_retry_at: float | None

    @property
    def can_trade(self) -> bool:
        return self.state is ConnectivityState.HEALTHY


class BrokerConnectivitySupervisor:
    """Fail-closed broker connectivity state machine.

    This class only decides connectivity/trading eligibility. It never places,
    cancels, or retries orders itself.
    """

    def __init__(self, *, max_failures: int = 3, base_backoff_seconds: float = 1.0, max_backoff_seconds: float = 60.0):
        if max_failures < 1 or base_backoff_seconds <= 0 or max_backoff_seconds < base_backoff_seconds:
            raise ValueError("invalid connectivity backoff configuration")
        self.max_failures = max_failures
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self._state = ConnectivityState.DISCONNECTED
        self._failures = 0
        self._last_success_at: float | None = None
        self._next_retry_at: float | None = None

    @staticmethod
    def _validate_now(now: float) -> float:
        value = float(now)
        if not math.isfinite(value):
            raise ValueError("connectivity timestamp must be finite")
        return value

    def success(self, now: float) -> ConnectivitySnapshot:
        now = self._validate_now(now)
        self._failures = 0
        self._last_success_at = now
        self._next_retry_at = None
        self._state = ConnectivityState.HEALTHY
        return self.snapshot()

    def record_success(self, now: float | None = None) -> ConnectivitySnapshot:
        """Record a successful broker interaction using a real timestamp by default."""
        return self.success(time.time() if now is None else now)

    def failure(self, now: float) -> ConnectivitySnapshot:
        now = self._validate_now(now)
        self._failures += 1
        self._state = ConnectivityState.DEGRADED if self._failures < self.max_failures else ConnectivityState.DISCONNECTED
        delay = min(self.base_backoff_seconds * (2 ** (self._failures - 1)), self.max_backoff_seconds)
        self._next_retry_at = now + delay
        return self.snapshot()

    def begin_recovery(self, now: float) -> ConnectivitySnapshot:
        now = self._validate_now(now)
        if self._next_retry_at is not None and now < self._next_retry_at:
            return self.snapshot()
        self._state = ConnectivityState.RECOVERING
        return self.snapshot()

    def snapshot(self) -> ConnectivitySnapshot:
        return ConnectivitySnapshot(self._state, self._failures, self._last_success_at, self._next_retry_at)
