import asyncio

import pytest

from app.market_data import Instrument
from app.market_data.realtime import RealtimeTickStream
from app.market_data.reconnect import ConnectionState, RealtimeConnectionState
from app.market_data.upstox_stream import UpstoxMarketDataStream


INSTRUMENT = Instrument(symbol="RELIANCE", exchange="NSE")
KEY = "NSE_EQ|12345"


class FakeStreamer:
    def __init__(self):
        self.handlers = {}
        self.calls = []

    def on(self, event, handler):
        self.handlers[event] = handler

    def connect(self):
        self.calls.append(("connect",))

    def subscribe(self, keys, mode):
        self.calls.append(("subscribe", keys, mode))

    def unsubscribe(self, keys):
        self.calls.append(("unsubscribe", keys))

    def change_mode(self, keys, mode):
        self.calls.append(("change_mode", keys, mode))

    def disconnect(self):
        self.calls.append(("disconnect",))


@pytest.mark.asyncio
async def test_lifecycle_and_subscription_are_forwarded():
    fake = FakeStreamer()
    ticks = RealtimeTickStream()
    state = RealtimeConnectionState()
    stream = UpstoxMarketDataStream(fake, {KEY: INSTRUMENT}, ticks, connection_state=state)

    stream.connect()
    assert fake.calls == [("connect",)]
    fake.handlers["open"]()
    assert stream.connected
    assert state.snapshot(INSTRUMENT).state == ConnectionState.CONNECTED

    stream.subscribe([KEY])
    stream.change_mode([KEY], "full")
    stream.unsubscribe([KEY])
    assert ("subscribe", [KEY], "ltpc") in fake.calls
    assert ("change_mode", [KEY], "full") in fake.calls
    assert ("unsubscribe", [KEY]) in fake.calls


@pytest.mark.asyncio
async def test_close_and_error_fail_closed():
    fake = FakeStreamer()
    ticks = RealtimeTickStream()
    state = RealtimeConnectionState()
    stream = UpstoxMarketDataStream(fake, {KEY: INSTRUMENT}, ticks, connection_state=state)
    stream.connect()
    fake.handlers["open"]()
    fake.handlers["close"]()
    assert state.snapshot(INSTRUMENT).state == ConnectionState.DISCONNECTED
    assert not state.snapshot(INSTRUMENT).health.value == "healthy"

    fake.handlers["open"]()
    fake.handlers["error"](RuntimeError("socket"))
    assert state.snapshot(INSTRUMENT).state == ConnectionState.DISCONNECTED


def test_operations_require_connection():
    fake = FakeStreamer()
    stream = UpstoxMarketDataStream(fake, {KEY: INSTRUMENT}, RealtimeTickStream())
    with pytest.raises(RuntimeError):
        stream.subscribe([KEY])


def test_disconnect_forwards_and_fails_closed():
    fake = FakeStreamer()
    state = RealtimeConnectionState()
    stream = UpstoxMarketDataStream(fake, {KEY: INSTRUMENT}, RealtimeTickStream(), connection_state=state)
    stream.connect()
    fake.handlers["open"]()
    stream.disconnect()
    assert ("disconnect",) in fake.calls
    assert state.snapshot(INSTRUMENT).state == ConnectionState.DISCONNECTED


def test_invalid_mode_is_rejected():
    with pytest.raises(ValueError):
        UpstoxMarketDataStream(FakeStreamer(), {KEY: INSTRUMENT}, RealtimeTickStream(), mode="bad")
