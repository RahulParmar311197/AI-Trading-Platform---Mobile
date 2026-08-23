from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RateLimit:
    requests: int
    window_seconds: float

    def __post_init__(self) -> None:
        if self.requests < 1 or self.window_seconds <= 0:
            raise ValueError("invalid rate limit")


class AsyncRateLimiter:
    def __init__(self, limit: RateLimit, clock: Callable[[], float] | None = None):
        self.limit = limit
        self._clock = clock or time.monotonic
        self._events: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = self._clock()
                cutoff = now - self.limit.window_seconds
                while self._events and self._events[0] <= cutoff:
                    self._events.popleft()
                if len(self._events) < self.limit.requests:
                    self._events.append(now)
                    return
                delay = max(0.0, self._events[0] + self.limit.window_seconds - now)
            await asyncio.sleep(delay)


class RetryPolicy:
    def __init__(self, max_attempts: int = 3, base_delay: float = 0.25, max_delay: float = 4.0):
        if max_attempts < 1 or base_delay < 0 or max_delay < base_delay:
            raise ValueError("invalid retry policy")
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def run(self, operation: Callable[[], Awaitable[T]], should_retry: Callable[[Exception], bool]) -> T:
        last: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                return await operation()
            except Exception as exc:
                last = exc
                if attempt + 1 >= self.max_attempts or not should_retry(exc):
                    raise
                await asyncio.sleep(min(self.max_delay, self.base_delay * (2**attempt)))
        raise RuntimeError("retry operation failed") from last
