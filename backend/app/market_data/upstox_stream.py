from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .models import Instrument, Tick
from .realtime import RealtimeTickStream
from .upstox import UpstoxMarketDataNormalizer


class UpstoxMarketDataStream:
    """Transport boundary around Upstox MarketDataStreamerV3.

    The SDK object is injected so tests never require credentials or a live
    socket. Broker callbacks are translated to canonical ticks and published
    only after normalization succeeds.
    """

    def __init__(
        self,
        streamer: Any,
        instruments: Mapping[str, Instrument],
        tick_stream: RealtimeTickStream,
        *,
        mode: str = "ltpc",
    ) -> None:
        if mode not in {"ltpc", "full", "option_greeks", "full_d30"}:
            raise ValueError("unsupported Upstox market-data mode")
        self._streamer = streamer
        self._normalizer = UpstoxMarketDataNormalizer(instruments)
        self._tick_stream = tick_stream
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
        self._streamer.connect()

    def _on_open(self, *args: Any, **kwargs: Any) -> None:
        self._connected = True

    async def _publish(self, ticks: Sequence[Tick]) -> None:
        for tick in ticks:
            await self._tick_stream.publish(tick)

    def _on_message(self, message: Any) -> None:
        if isinstance(message, Mapping):
            ticks = self._normalizer.normalize(message)
            if ticks:
                # The SDK callback is synchronous; schedule publication when
                # an event loop is available rather than blocking the socket.
                import asyncio
                loop = asyncio.get_running_loop()
                loop.create_task(self._publish(ticks))

    def _on_close(self, *args: Any, **kwargs: Any) -> None:
        self._connected = False

    def _on_error(self, *args: Any, **kwargs: Any) -> None:
        self._connected = False

    def subscribe(self, instrument_keys: Sequence[str]) -> None:
        if not self._connected:
            raise RuntimeError("Upstox market-data stream is not connected")
        self._streamer.subscribe(list(instrument_keys), self._mode)

    def unsubscribe(self, instrument_keys: Sequence[str]) -> None:
        if not self._connected:
            raise RuntimeError("Upstox market-data stream is not connected")
        self._streamer.unsubscribe(list(instrument_keys))

    def change_mode(self, instrument_keys: Sequence[str], mode: str) -> None:
        if mode not in {"ltpc", "full", "option_greeks", "full_d30"}:
            raise ValueError("unsupported Upstox market-data mode")
        if not self._connected:
            raise RuntimeError("Upstox market-data stream is not connected")
        self._streamer.change_mode(list(instrument_keys), mode)

    def disconnect(self) -> None:
        disconnect = getattr(self._streamer, "disconnect", None)
        if callable(disconnect):
            disconnect()
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected
