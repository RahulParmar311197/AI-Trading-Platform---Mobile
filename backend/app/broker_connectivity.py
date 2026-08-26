from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BrokerConnectionState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"
    RECOVERING = "RECOVERING"


@dataclass(frozen=True)
class ConnectivitySnapshot:
    state: BrokerConnectionState
    failures: int
    last_success_at: float | None
    next_retry_at: float | None

    @property
    def can_trade(self) -> bool:
        return self.state is BrokerConnectionState.HEALTHY


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
        self._state = BrokerConnectionState.DISCONNECTED
        self._failures = 0
        self._last_success_at: float | None = None
        self._next_retry_at: float | None = None

    def success(self, now: float) -> ConnectivitySnapshot:
        self._failures = 0
        self._last_success_at = now
        self._next_retry_at = None
        self._state = BrokerConnectionState.HEALTHY
        return self.snapshot()

    def failure(self, now: float) -> ConnectivitySnapshot:
        self._failures += 1
        self._state = (
            BrokerConnectionState.DEGRADED
            if self._failures < self.max_failures
            else BrokerConnectionState.DISCONNECTED
        )
        delay = min(self.base_backoff_seconds * (2 ** (self._failures - 1)), self.max_backoff_seconds)
        self._next_retry_at = now + delay
        return self.snapshot()

    def begin_recovery(self, now: float) -> ConnectivitySnapshot:
        if self._next_retry_at is not None and now < self._next_retry_at:
            return self.snapshot()
        self._state = BrokerConnectionState.RECOVERING
        return self.snapshot()

    def snapshot(self) -> ConnectivitySnapshot:
        return ConnectivitySnapshot(
            state=self._state,
            failures=self._failures,
            last_success_at=self._last_success_at,
            next_retry_at=self._next_retry_at,
        )
