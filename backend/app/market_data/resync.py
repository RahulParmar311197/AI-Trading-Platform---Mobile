from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .historical import load_historical_candles
from .models import Instrument, Timeframe
from .provider import HistoricalMarketDataProvider
from .reconnect import RealtimeConnectionState
from .repository import HistoricalCandleRepository


@dataclass(frozen=True)
class ResyncResult:
    candles_loaded: int
    ready: bool


class MarketDataResynchronizer:
    """Repairs history before reopening strategy flow."""

    def __init__(
        self,
        historical_provider: HistoricalMarketDataProvider,
        repository: HistoricalCandleRepository,
        connection_state: RealtimeConnectionState,
    ) -> None:
        self._provider = historical_provider
        self._repository = repository
        self._state = connection_state

    async def resync(
        self,
        instrument: Instrument,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        resume_sequence: int,
    ) -> ResyncResult:
        if end < start:
            raise ValueError("resync end must not precede start")
        if resume_sequence < 0:
            raise ValueError("resume_sequence must be non-negative")

        self._state.sequence_gap(instrument)
        try:
            loaded = await load_historical_candles(
                self._provider,
                self._repository,
                instrument,
                timeframe,
                start,
                end,
                replace=True,
            )
        except Exception:
            # Never promote an instrument to READY after an incomplete repair.
            return ResyncResult(candles_loaded=0, ready=False)

        self._state.resynced(instrument, resume_sequence)
        return ResyncResult(candles_loaded=loaded, ready=True)
