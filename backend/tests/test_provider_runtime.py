import asyncio
from datetime import datetime, timezone

import pytest

from app.data_provider import MarketDataProvider, ProviderCandle, ProviderError
from app.provider_config import ProviderConfig
from app.provider_runtime import ProviderRuntime


class FlakyProvider(MarketDataProvider):
    name = "test"

    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    async def historical(self, symbol, timeframe, start, end):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("temporary provider failure")
        return [
            ProviderCandle(
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                100,
                101,
                99,
                100.5,
                10,
            )
        ]


@pytest.mark.asyncio
async def test_provider_runtime_retries_transient_failure():
    provider = FlakyProvider(failures=2)
    config = ProviderConfig(
        name="test",
        base_url="http://example.test",
        rate_limit_per_second=1000,
        retry_attempts=3,
        retry_base_delay_seconds=0.001,
    )
    result = await ProviderRuntime(provider, config).historical(
        "NIFTY", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc), "5m"
    )
    assert len(result) == 1
    assert provider.calls == 3


@pytest.mark.asyncio
async def test_provider_runtime_exhausts_retries():
    provider = FlakyProvider(failures=5)
    config = ProviderConfig(
        name="test",
        base_url="http://example.test",
        rate_limit_per_second=1000,
        retry_attempts=2,
        retry_base_delay_seconds=0.001,
    )
    with pytest.raises(ProviderError, match="failed after 2 attempts"):
        await ProviderRuntime(provider, config).historical(
            "NIFTY", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc), "5m"
        )
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_provider_runtime_does_not_swallow_cancellation():
    provider = FlakyProvider(failures=5)
    config = ProviderConfig(
        name="test",
        base_url="http://example.test",
        rate_limit_per_second=1000,
        retry_attempts=3,
        retry_base_delay_seconds=0.01,
    )
    task = asyncio.create_task(
        ProviderRuntime(provider, config).historical(
            "NIFTY", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc), "5m"
        )
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
