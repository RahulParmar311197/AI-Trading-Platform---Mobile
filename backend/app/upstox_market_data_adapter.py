from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator, Callable, Sequence

from app.market_data_adapter import MarketDataAdapter, MarketTick


class UpstoxMarketDataAdapter(MarketDataAdapter):
    """Upstox Market Data Feed V3 adapter using the official Python SDK."""

    def __init__(
        self,
        access_token: str,
        instrument_keys: Sequence[str] | None = None,
        mode: str = "ltpc",
        streamer_factory: Callable | None = None,
    ) -> None:
        if not access_token:
            raise ValueError("access_token is required")
        if mode not in {"ltpc", "full", "option_greeks", "full_d30"}:
            raise ValueError(f"unsupported Upstox market-data mode: {mode}")

        self._access_token = access_token
        self._instrument_keys = list(instrument_keys or [])
        self._mode = mode
        self._streamer_factory = streamer_factory
        self._streamer = None
        self._queue: asyncio.Queue[MarketTick] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected = False
        self._closed = False

    def _build_streamer(self):
        if self._streamer_factory is not None:
            return self._streamer_factory(self._access_token, self._instrument_keys, self._mode)

        try:
            import upstox_client
        except ImportError as exc:
            raise RuntimeError(
                "Upstox market streaming requires upstox-python-sdk"
            ) from exc

        configuration = upstox_client.Configuration()
        configuration.access_token = self._access_token
        api_client = upstox_client.ApiClient(configuration)
        return upstox_client.MarketDataStreamerV3(
            api_client,
            self._instrument_keys,
            self._mode,
        )

    def _emit_message(self, message) -> None:
        if self._closed or self._loop is None:
            return
        if not isinstance(message, dict):
            return

        feeds = message.get("feeds") or {}
        for symbol, feed in feeds.items():
            ltpc = feed.get("ltpc") if isinstance(feed, dict) else None
            if not isinstance(ltpc, dict):
                continue

            price = ltpc.get("ltp")
            timestamp_ms = ltpc.get("ltt")
            if price is None or timestamp_ms is None:
                continue

            try:
                timestamp = datetime.fromtimestamp(
                    int(timestamp_ms) / 1000, tz=timezone.utc
                )
                tick = MarketTick(
                    symbol=str(symbol),
                    timestamp=timestamp,
                    price=float(price),
                    volume=float(ltpc.get("ltq") or 0),
                )
            except (TypeError, ValueError, OverflowError):
                continue

            self._loop.call_soon_threadsafe(self._queue.put_nowait, tick)

    async def connect(self) -> None:
        if self._connected:
            return
        self._loop = asyncio.get_running_loop()
        self._closed = False
        self._streamer = self._build_streamer()
        self._streamer.on("message", self._emit_message)
        self._streamer.connect()
        self._connected = True

    async def subscribe(self, symbols: Sequence[str]) -> None:
        if not self._connected or self._streamer is None:
            raise RuntimeError("market-data adapter is not connected")
        keys = list(symbols)
        if not keys:
            return
        self._streamer.subscribe(keys, self._mode)
        for key in keys:
            if key not in self._instrument_keys:
                self._instrument_keys.append(key)

    async def unsubscribe(self, symbols: Sequence[str]) -> None:
        if self._streamer is None:
            return
        keys = list(symbols)
        if not keys:
            return
        self._streamer.unsubscribe(keys)
        self._instrument_keys = [key for key in self._instrument_keys if key not in keys]

    async def stream_ticks(self) -> AsyncIterator[MarketTick]:
        if not self._connected:
            raise RuntimeError("market-data adapter is not connected")
        while not self._closed:
            yield await self._queue.get()

    async def close(self) -> None:
        self._closed = True
        self._connected = False
        if self._streamer is not None:
            self._streamer.disconnect()
        self._streamer = None
        self._loop = None
