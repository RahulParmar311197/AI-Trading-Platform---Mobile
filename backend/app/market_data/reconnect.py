from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import Instrument
from .realtime_quality import StreamHealth, TickSequenceTracker


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RESYNC_REQUIRED = "resync_required"
    READY = "ready"


@dataclass(frozen=True)
class ConnectionSnapshot:
    state: ConnectionState
    health: StreamHealth
    reconnect_attempts: int


class RealtimeConnectionState:
    """Fail-closed connection/resync state for realtime market data."""

    def __init__(self, tracker: TickSequenceTracker | None = None) -> None:
        self._tracker = tracker or TickSequenceTracker()
        self._states: dict[Instrument, ConnectionSnapshot] = {}

    def begin_connect(self, instrument: Instrument) -> None:
        previous = self._states.get(instrument)
        attempts = 1 if previous is None else previous.reconnect_attempts + 1
        self._states[instrument] = ConnectionSnapshot(
            ConnectionState.CONNECTING, StreamHealth.DEGRADED, attempts
        )

    def connected(self, instrument: Instrument) -> None:
        snapshot = self._states.get(instrument)
        attempts = snapshot.reconnect_attempts if snapshot else 0
        self._states[instrument] = ConnectionSnapshot(
            ConnectionState.CONNECTED, StreamHealth.DEGRADED, attempts
        )

    def sequence_gap(self, instrument: Instrument) -> None:
        snapshot = self._states.get(instrument)
        attempts = snapshot.reconnect_attempts if snapshot else 0
        self._states[instrument] = ConnectionSnapshot(
            ConnectionState.RESYNC_REQUIRED, StreamHealth.RESYNC_REQUIRED, attempts
        )

    def resynced(self, instrument: Instrument, sequence: int) -> None:
        self._tracker.mark_resynced(instrument, sequence)
        snapshot = self._states.get(instrument)
        attempts = snapshot.reconnect_attempts if snapshot else 0
        self._states[instrument] = ConnectionSnapshot(
            ConnectionState.READY, StreamHealth.HEALTHY, attempts
        )

    def disconnected(self, instrument: Instrument) -> None:
        snapshot = self._states.get(instrument)
        attempts = snapshot.reconnect_attempts if snapshot else 0
        self._states[instrument] = ConnectionSnapshot(
            ConnectionState.DISCONNECTED, StreamHealth.DEGRADED, attempts
        )

    def snapshot(self, instrument: Instrument) -> ConnectionSnapshot:
        return self._states.get(
            instrument,
            ConnectionSnapshot(ConnectionState.DISCONNECTED, StreamHealth.DEGRADED, 0),
        )

    def can_publish_to_strategy(self, instrument: Instrument) -> bool:
        return self.snapshot(instrument).state == ConnectionState.READY
