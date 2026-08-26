from datetime import datetime, timezone

import pytest

from app.market_data_adapter import MarketDataAdapter, MarketTick


class DummyMarketDataAdapter(MarketDataAdapter):
    def __init__(self):
        self.connected = False
        self.subscriptions = set()
        self.closed = False

    async def connect(self):
        self.connected = True

    async def subscribe(self, symbols):
        if not self.connected:
            raise RuntimeError("market-data adapter is not connected")
        self.subscriptions.update(symbols)

    async def unsubscribe(self, symbols):
        self.subscriptions.difference_update(symbols)

    async def stream_ticks(self):
        if not self.connected:
            raise RuntimeError("market-data adapter is not connected")
        if False:
            yield None

    async def close(self):
        self.closed = True
        self.connected = False


def test_market_tick_is_normalized_data_contract():
    ts = datetime.now(timezone.utc)
    tick = MarketTick(symbol="NSE_EQ|INE002A01018", timestamp=ts, price=123.45, volume=10)

    assert tick.symbol
    assert tick.timestamp == ts
    assert tick.price == 123.45
    assert tick.volume == 10


@pytest.mark.asyncio
async def test_adapter_requires_connection_before_subscription():
    adapter = DummyMarketDataAdapter()

    with pytest.raises(RuntimeError, match="not connected"):
        await adapter.subscribe(["NSE_EQ|INE002A01018"])


@pytest.mark.asyncio
async def test_adapter_subscription_and_shutdown_lifecycle():
    adapter = DummyMarketDataAdapter()
    await adapter.connect()
    await adapter.subscribe(["A", "B"])

    assert adapter.connected is True
    assert adapter.subscriptions == {"A", "B"}

    await adapter.unsubscribe(["A"])
    assert adapter.subscriptions == {"B"}

    await adapter.close()
    assert adapter.connected is False
    assert adapter.closed is True
