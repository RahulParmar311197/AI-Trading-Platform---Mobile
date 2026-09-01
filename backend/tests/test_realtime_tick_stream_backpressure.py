import asyncio
from datetime import datetime, timezone

import pytest

from app.market_data.models import Instrument, Tick
from app.market_data.realtime import RealtimeMarketDataBackpressure, RealtimeTickStream


@pytest.mark.asyncio
async def test_publish_delivers_to_all_subscribers_without_dropping() -> None:
    stream = RealtimeTickStream(max_queue_size=2)
    instrument = Instrument(symbol="NIFTY", exchange="NSE")
    _, first = await stream.subscribe([instrument])
    _, second = await stream.subscribe([instrument])
    tick = Tick(
        instrument=instrument,
        timestamp=datetime.now(timezone.utc),
        price=100.0,
    )

    assert await stream.publish(tick) == 2
    assert await first.__anext__() == tick
    assert await second.__anext__() == tick
    await stream.close()


@pytest.mark.asyncio
async def test_full_subscriber_fails_closed_without_partial_delivery() -> None:
    stream = RealtimeTickStream(max_queue_size=1)
    instrument = Instrument(symbol="NIFTY", exchange="NSE")
    _, first = await stream.subscribe([instrument])
    _, second = await stream.subscribe([instrument])
    tick_one = Tick(
        instrument=instrument,
        timestamp=datetime.now(timezone.utc),
        price=100.0,
    )
    tick_two = tick_one.model_copy(update={"price": 101.0})

    assert await stream.publish(tick_one) == 2
    with pytest.raises(RealtimeMarketDataBackpressure, match="queue is full"):
        await stream.publish(tick_two)

    # The failed publish is atomic: neither subscriber receives tick_two.
    assert await first.__anext__() == tick_one
    assert await second.__anext__() == tick_one
    with pytest.raises(RealtimeMarketDataBackpressure):
        await stream.publish(tick_two)
    await stream.close()


@pytest.mark.asyncio
async def test_invalid_queue_size_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_queue_size must be positive"):
        RealtimeTickStream(max_queue_size=0)
