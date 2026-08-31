from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

from .models import Instrument, Tick
from .provider import RealtimeMarketDataProvider


class RealtimeTickStream(RealtimeMarketDataProvider):
    """Provider-neutral realtime tick fan-out.

    Broker adapters publish already-normalized Tick objects. Subscribers get
    their own queue, so a slow consumer cannot consume another consumer's
    events. The stream is intentionally unbounded at this layer; production
    adapters can impose provider-specific backpressure before publishing.
    """

    def __init__(self) -> None:
        self._subscriptions: dict[int, asyncio.Queue[Tick | None]] = {}
        self._next_id = 0
        self._lock = asyncio.Lock()

    async def subscribe(self, instruments: Sequence[Instrument]) -> tuple[int, AsyncIterator[Tick]]:
        allowed = frozenset(instruments)
        queue: asyncio.Queue[Tick | None] = asyncio.Queue()
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
        if queue is not None:
            queue.put_nowait(None)

    async def publish(self, tick: Tick) -> int:
        async with self._lock:
            queues = tuple(self._subscriptions.values())
        delivered = 0
        for queue in queues:
            queue.put_nowait(tick)
            delivered += 1
        return delivered

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
            queue.put_nowait(None)
