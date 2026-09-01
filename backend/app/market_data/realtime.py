from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

from .models import Instrument, Tick
from .provider import RealtimeMarketDataProvider


class RealtimeMarketDataBackpressure(RuntimeError):
    """Raised when a realtime subscriber cannot accept the next tick safely."""


class RealtimeTickStream(RealtimeMarketDataProvider):
    """Provider-neutral realtime tick fan-out with bounded backpressure.

    Broker adapters publish already-normalized Tick objects. Subscribers get
    their own bounded queue, so a slow consumer cannot consume another
    consumer's events or grow process memory without limit.

    A full subscriber fails the entire publish atomically instead of dropping
    a tick for one consumer while delivering it to others. Callers must treat
    this as a data-quality/safety signal and recover or halt the affected
    realtime pipeline; ticks are never silently discarded here.
    """

    def __init__(self, *, max_queue_size: int = 1024) -> None:
        if max_queue_size <= 0:
            raise ValueError("max_queue_size must be positive")
        self._max_queue_size = max_queue_size
        self._subscriptions: dict[int, asyncio.Queue[Tick | None]] = {}
        self._next_id = 0
        self._lock = asyncio.Lock()

    async def subscribe(self, instruments: Sequence[Instrument]) -> tuple[int, AsyncIterator[Tick]]:
        allowed = frozenset(instruments)
        queue: asyncio.Queue[Tick | None] = asyncio.Queue(maxsize=self._max_queue_size)
        async with self._lock:
            subscription_id = self._next_id
            self._next_id += 1
            self._subscriptions[subscription_id] = queue

        async def iterator() -> AsyncIterator[Tick]:
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        return
                    if item.instrument in allowed:
                        yield item
            finally:
                await self.unsubscribe(subscription_id)

        return subscription_id, iterator()

    async def unsubscribe(self, subscription_id: int) -> None:
        async with self._lock:
            queue = self._subscriptions.pop(subscription_id, None)
        if queue is not None and not queue.full():
            queue.put_nowait(None)

    async def publish(self, tick: Tick) -> int:
        async with self._lock:
            queues = tuple(self._subscriptions.values())
            if any(queue.full() for queue in queues):
                raise RealtimeMarketDataBackpressure(
                    "realtime subscriber queue is full; refusing to drop market data"
                )
            for queue in queues:
                queue.put_nowait(tick)
        return len(queues)

    def ticks(self, instruments: Sequence[Instrument]) -> AsyncIterator[Tick]:
        async def stream() -> AsyncIterator[Tick]:
            _, iterator = await self.subscribe(instruments)
            async for tick in iterator:
                yield tick

        return stream()

    async def close(self) -> None:
        async with self._lock:
            subscriptions = tuple(self._subscriptions.items())
            self._subscriptions.clear()
        for _, queue in subscriptions:
            if not queue.full():
                queue.put_nowait(None)
