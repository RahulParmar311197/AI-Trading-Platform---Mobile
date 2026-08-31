from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any, Awaitable, Callable

from .models import Instrument, Tick
from .realtime import RealtimeTickStream
from .reconnect import RealtimeConnectionState
from .reconnect_controller import ReconnectController
from .upstox import UpstoxMarketDataNormalizer


class UpstoxMarketDataStream:
    """Upstox transport with single-flight reconnect and fail-closed recovery."""

    VALID_MODES = {"ltpc", "full", "option_greeks", "full_d30"}

    def __init__(self, streamer: Any, instruments: Mapping[str, Instrument], tick_stream: RealtimeTickStream, *, mode: str = "ltpc", connection_state: RealtimeConnectionState | None = None, recovery: Callable[[], Awaitable[bool]] | None = None, reconnect_factory: Callable[[Callable[[], Any]], ReconnectController] | None = None) -> None:
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
        self._recovery = recovery
        self._reconnect_factory = reconnect_factory or (lambda connect: ReconnectController(connect))
        self._recovery_task: asyncio.Task[bool] | None = None

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
        self._mark_disconnected_and_recover()

    def _on_error(self, *args: Any, **kwargs: Any) -> None:
        self._mark_disconnected_and_recover()

    def _mark_disconnected_and_recover(self) -> None:
        self._connected = False
        for instrument in self._instrument_by_key.values():
            self._connection_state.disconnected(instrument)
        if self._recovery is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._recovery_task is None or self._recovery_task.done():
            controller = self._reconnect_factory(self._streamer.connect)
            self._recovery_task = loop.create_task(self._run_recovery(controller))

    async def _run_recovery(self, controller: ReconnectController) -> bool:
        result = await controller.run()
        if not result or self._recovery is None:
            return False
        try:
            return bool(await self._recovery())
        except Exception:
            return False

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
        if self._recovery_task is not None and not self._recovery_task.done():
            self._recovery_task.cancel()
        disconnect = getattr(self._streamer, "disconnect", None)
        if callable(disconnect):
            disconnect()
        self._connected = False
        for instrument in self._instrument_by_key.values():
            self._connection_state.disconnected(instrument)

    @property
    def connected(self) -> bool:
        return self._connected
