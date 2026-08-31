from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import Instrument, Tick


class StreamHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RESYNC_REQUIRED = "resync_required"


@dataclass(frozen=True)
class SequenceObservation:
    accepted: bool
    duplicate: bool
    gap: bool
    expected: int | None
    received: int | None
    health: StreamHealth


class TickSequenceTracker:
    """Fail-closed sequence tracker for provider feeds that expose sequence IDs."""

    def __init__(self) -> None:
        self._last: dict[Instrument, int] = {}
        self._health: dict[Instrument, StreamHealth] = {}

    def observe(self, instrument: Instrument, sequence: int) -> SequenceObservation:
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        last = self._last.get(instrument)
        if last is None:
            self._last[instrument] = sequence
            self._health[instrument] = StreamHealth.HEALTHY
            return SequenceObservation(True, False, False, None, sequence, StreamHealth.HEALTHY)
        expected = last + 1
        if sequence == last:
            return SequenceObservation(False, True, False, expected, sequence, self._health[instrument])
        if sequence < expected:
            self._health[instrument] = StreamHealth.RESYNC_REQUIRED
            return SequenceObservation(False, False, True, expected, sequence, StreamHealth.RESYNC_REQUIRED)
        self._last[instrument] = sequence
        self._health[instrument] = StreamHealth.RESYNC_REQUIRED
        return SequenceObservation(False, False, True, expected, sequence, StreamHealth.RESYNC_REQUIRED)

    def mark_resynced(self, instrument: Instrument, sequence: int) -> None:
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        self._last[instrument] = sequence
        self._health[instrument] = StreamHealth.HEALTHY

    def health(self, instrument: Instrument) -> StreamHealth:
        return self._health.get(instrument, StreamHealth.HEALTHY)

    def reset(self, instrument: Instrument) -> None:
        self._last.pop(instrument, None)
        self._health.pop(instrument, None)
