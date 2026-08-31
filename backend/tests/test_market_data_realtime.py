import asyncio
from datetime import datetime, timezone

import pytest

from app.market_data import Instrument, Tick
from app.market_data.realtime import RealtimeTickStream


INSTRUMENT = Instrument(symbol="RELIANCE", exchange="NSE")
OTHER = Instrument(symbol="INFY", exchange="NSE")


def make_tick(instrument=INSTRUMENT, price=100):
    return Tick(
        instrument=instrument,
        timestamp=datetime(2026, 8, 31, 9, 15, tzinfo=timezone.utc),
        price=price,
        volume=1,
    )


@pytest.mark.asyncio
async def test_subscriber_receives_only_requested_instrument():
    stream = RealtimeTickStream()
    _, iterator = await stream.subscribe([INSTRUMENT])

    await stream.publish(make_tick(OTHER, 200))
    await stream.publish(make_tick(INSTRUMENT, 101))

    received = await asyncio.wait_for(iterator.__anext__(), timeout=0.5)
    assert received.instrument == INSTRUMENT
    assert received.price == 101
    await stream.close()


@pytest.mark.asyncio
async def test_multiple_subscribers_are_independently_delivered():
    stream = RealtimeTickStream()
    _, first = await stream.subscribe([INSTRUMENT])
    _, second = await stream.subscribe([INSTRUMENT])

    assert await stream.publish(make_tick(price=105)) == 2
    assert (await asyncio.wait_for(first.__anext__(), timeout=0.5)).price == 105
    assert (await asyncio.wait_for(second.__anext__(), timeout=0.5)).price == 105
    await stream.close()


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    stream = RealtimeTickStream()
    subscription_id, iterator = await stream.subscribe([INSTRUMENT])
    await stream.unsubscribe(subscription_id)

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(iterator.__anext__(), timeout=0.5)


@pytest.mark.asyncio
async def test_close_terminates_all_subscribers():
    stream = RealtimeTickStream()
    _, iterator = await stream.subscribe([INSTRUMENT])
    await stream.close()

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(iterator.__anext__(), timeout=0.5)
