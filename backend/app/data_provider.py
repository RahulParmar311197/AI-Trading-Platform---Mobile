from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderCandle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataProvider(ABC):
    name: str = "base"

    def __init__(self, config=None):
        self.config = config

    @abstractmethod
    async def historical(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[ProviderCandle]:
        ...


class RetryPolicy:
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 8.0,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if base_delay < 0:
            raise ValueError("base_delay must be >= 0")
        if max_delay < 0:
            raise ValueError("max_delay must be >= 0")

        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def run(
        self,
        fn: Callable[[], Awaitable[Any]],
    ):
        last: Exception | None = None

        for attempt in range(self.max_attempts):
            try:
                return await fn()
            except Exception as exc:
                last = exc

                if attempt + 1 < self.max_attempts:
                    delay = min(
                        self.max_delay,
                        self.base_delay * (2**attempt),
                    )
                    if delay:
                        await asyncio.sleep(delay)

        raise ProviderError(str(last)) from last


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, MarketDataProvider] = {}

    def register(self, provider: MarketDataProvider):
        if provider.name in self._providers:
            raise ValueError(
                f"provider already registered: {provider.name}"
            )

        self._providers[provider.name] = provider

    def get(self, name: str) -> MarketDataProvider:
        if name not in self._providers:
            raise KeyError(
                f"provider not registered: {name}"
            )

        return self._providers[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))


class CachedProvider:
    def __init__(self, provider: MarketDataProvider):
        self.provider = provider
        self.cache: dict[tuple, list[ProviderCandle]] = {}

    async def historical(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[ProviderCandle]:
        key = (symbol, timeframe, start, end)

        if key not in self.cache:
            rows = await self.provider.historical(
                symbol,
                timeframe,
                start,
                end,
            )

            seen = set()
            clean = []

            for candle in sorted(
                rows,
                key=lambda x: x.timestamp,
            ):
                if candle.timestamp not in seen:
                    seen.add(candle.timestamp)
                    clean.append(candle)

            self.cache[key] = clean

        return list(self.cache[key])


class PaginatedProvider:
    def __init__(
        self,
        fetch_page,
        page_size: int = 1000,
        max_pages: int = 100,
    ):
        if page_size < 1:
            raise ValueError("page_size must be >= 1")
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")

        self.fetch_page = fetch_page
        self.page_size = page_size
        self.max_pages = max_pages

    async def historical(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[ProviderCandle]:
        result: list[ProviderCandle] = []
        cursor = None

        for _ in range(self.max_pages):
            page, cursor = await self.fetch_page(
                symbol,
                timeframe,
                start,
                end,
                cursor,
                self.page_size,
            )

            result.extend(page)

            if not cursor:
                break
        else:
            raise ProviderError(
                "historical data pagination limit exceeded"
            )

        seen = set()
        clean = []

        for candle in sorted(
            result,
            key=lambda x: x.timestamp,
        ):
            if candle.timestamp not in seen:
                seen.add(candle.timestamp)
                clean.append(candle)

        return clean