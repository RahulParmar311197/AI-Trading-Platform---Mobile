from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from .models import Instrument, Tick
from .realtime import RealtimeTickStream
from .reconnect import RealtimeConnectionState
from .upstox import UpstoxMarketDataNormalizer


class UpstoxMarketDataStream:
    """Transport boundary around Upstox MarketDataStreamerV3.

    Broker callbacks remain synchronous; normalized ticks are published to the
    provider-neutral stream. Connection failures fail closed through the
    realtime connection state so strategies cannot consume an unhealthy feed.
    """

    VALID_MODES = {"ltpc", "full", "option_greeks", "full_d30"}

    def __init__(
        self,
        streamer: Any,
        instruments: Mapping[str, Instrument],
        tick_stream: RealtimeTickStream,
        *,
        mode: str = "ltpc",
        connection_state: RealtimeConnectionState | None = None,
    ) -> None:
        if mode not in self.VALID_MODES:
            raise ValueError("unsupported Upstox market-data mode")
        self._streamer = streamer
        self._normalizer = UpstoxMarketDataNormalizer(instruments)
        self._tick_stream = tick_stream
        self._connection_state = connection_state or RealtimeConnectionState()
        self._instrument_by_key = dict(instruments)
        self._mode = mode
        self._connected = False
        self._handlers_registered = False

    def _register_handlers(self) -> None:
        if self._handlers_registered:
            return
        self._streamer.on("open", self._on_open)
        self._streamer.on("message", self._on_message)
        self._streamer.on("close", self._on_close)
        self._streamer.on("error", self._on_error)
        self._handlers_registered = True

    def connect(self) -> None:
        self._register_handlers()
        for instrument in self._instrument_by_key.values():
            self._connection_state.begin_connect(instrument)
        self._streamer.connect()

    def _on_open(self, *args: Any, **kwargs: Any) -> None:
        self._connected = True
        for instrument in self._instrument_by_key.values():
            self._connection_state.connected(instrument)

    async def _publish(self, ticks: Sequence[Tick]) -> None:
        for tick in ticks:
            if self._connection_state.can_publish_to_strategy(tick.instrument):
                await self._tick_stream.publish(tick)

    def _on_message(self, message: Any) -> None:
        if not isinstance(message, Mapping):
            return
        ticks = self._normalizer.normalize(message)
        if not ticks:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._publish(ticks))

    def _on_close(self, *args: Any, **kwargs: Any) -> None:
        self._connected = False
        for instrument in self._instrument_by_key.values():
            self._connection_state.disconnected(instrument)

    def _on_error(self, *args: Any, **kwargs: Any) -> None:
        self._connected = False
        for instrument in self._instrument_by_key.values():
            self._connection_state.disconnected(instrument)

    def subscribe(self, instrument_keys: Sequence[str]) -> None:
        if not self._connected:
            raise RuntimeError("Upstox market-data stream is not connected")
        self._streamer.subscribe(list(instrument_keys), self._mode)

    def unsubscribe(self, instrument_keys: Sequence[str]) -> None:
        if not self._connected:
            raise RuntimeError("Upstox market-data stream is not connected")
        self._streamer.unsubscribe(list(instrument_keys))

    def change_mode(self, instrument_keys: Sequence[str], mode: str) -> None:
        if mode not in self.VALID_MODES:
            raise ValueError("unsupported Upstox market-data mode")
        if not self._connected:
            raise RuntimeError("Upstox market-data stream is not connected")
        self._streamer.change_mode(list(instrument_keys), mode)

    def disconnect(self) -> None:
        disconnect = getattr(self._streamer, "disconnect", None)
        if callable(disconnect):
            disconnect()
        self._connected = False
        for instrument in self._instrument_by_key.values():
            self._connection_state.disconnected(instrument)

    @property
    def connected(self) -> bool:
        return self._connected
