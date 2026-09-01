from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass(frozen=True)
class BackoffPolicy:
    initial_seconds: float = 1.0
    max_seconds: float = 30.0
    multiplier: float = 2.0
    jitter_ratio: float = 0.2

    def delay(self, attempt: int, *, rng: random.Random | None = None) -> float:
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        if self.initial_seconds <= 0 or self.max_seconds <= 0:
            raise ValueError("backoff bounds must be positive")
        if self.multiplier < 1:
            raise ValueError("multiplier must be >= 1")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1")
        base = min(self.max_seconds, self.initial_seconds * self.multiplier ** (attempt - 1))
        generator = rng or random
        return min(self.max_seconds, base * (1 + generator.uniform(-self.jitter_ratio, self.jitter_ratio)))


class ReconnectController:
    """Bounded reconnect loop. A successful connect is not strategy-ready."""

    def __init__(self, connect, *, policy: BackoffPolicy | None = None, sleep=asyncio.sleep, max_attempts: int = 5):
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self._connect = connect
        self._policy = policy or BackoffPolicy()
        self._sleep = sleep
        self._max_attempts = max_attempts
        self._stop = asyncio.Event()
        self._attempt = 0

    @property
    def attempts(self) -> int:
        return self._attempt

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> bool:
        while not self._stop.is_set() and self._attempt < self._max_attempts:
            self._attempt += 1
            try:
                result = self._connect()
                if asyncio.iscoroutine(result):
                    result = await result
                if result is not False:
                    return True
            except Exception:
                pass
            if self._attempt < self._max_attempts:
                await self._sleep(self._policy.delay(self._attempt))
        return False


class ReconnectRecovery:
    """Connect, resync, then expose READY only after successful recovery."""

    def __init__(self, reconnect: ReconnectController, resync: Callable[[], Awaitable[bool]]):
        self._reconnect = reconnect
        self._resync = resync

    async def recover(self) -> bool:
        if not await self._reconnect.run():
            return False
        try:
            return bool(await self._resync())
        except Exception:
            return False
