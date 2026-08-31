import asyncio

import pytest

from app.market_data.models import Instrument
from app.market_data.realtime import RealtimeTickStream
from app.market_data.reconnect import ConnectionState, RealtimeConnectionState
from app.market_data.reconnect_controller import BackoffPolicy, ReconnectController
from app.market_data.upstox_stream import UpstoxMarketDataStream


KEY = "NSE_EQ|12345"
INSTRUMENT = Instrument(symbol="RELIANCE", exchange="NSE")


class FakeStreamer:
    def __init__(self):
        self.handlers = {}
        self.connect_calls = 0

    def on(self, event, handler):
        self.handlers[event] = handler

    def connect(self):
        self.connect_calls += 1

    def disconnect(self):
        pass

    def subscribe(self, keys, mode):
        pass

    def unsubscribe(self, keys):
        pass

    def change_mode(self, keys, mode):
        pass


@pytest.mark.asyncio
async def test_close_starts_single_reconnect_then_recovery():
    fake = FakeStreamer()
    state = RealtimeConnectionState()
    events = []

    async def recovery():
        events.append("resync")
        state.resynced(INSTRUMENT, 10)
        return True

    async def sleep(_):
        pass

    def factory(connect):
        return ReconnectController(connect, policy=BackoffPolicy(jitter_ratio=0), sleep=sleep)

    stream = UpstoxMarketDataStream(
        fake, {KEY: INSTRUMENT}, RealtimeTickStream(),
        connection_state=state, recovery=recovery, reconnect_factory=factory,
    )
    stream.connect()
    fake.handlers["open"]()
    fake.handlers["close"]()
    fake.handlers["error"]()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert fake.connect_calls == 2
    assert events == ["resync"]
    assert state.snapshot(INSTRUMENT).state == ConnectionState.READY


@pytest.mark.asyncio
async def test_recovery_failure_never_makes_ready():
    fake = FakeStreamer()
    state = RealtimeConnectionState()

    async def recovery():
        return False

    async def sleep(_):
        pass

    def factory(connect):
        return ReconnectController(connect, policy=BackoffPolicy(jitter_ratio=0), sleep=sleep)

    stream = UpstoxMarketDataStream(
        fake, {KEY: INSTRUMENT}, RealtimeTickStream(),
        connection_state=state, recovery=recovery, reconnect_factory=factory,
    )
    stream.connect()
    fake.handlers["open"]()
    fake.handlers["close"]()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert state.snapshot(INSTRUMENT).state != ConnectionState.READY
