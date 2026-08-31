import pytest

from app.market_data import Instrument
from app.market_data.realtime_quality import StreamHealth
from app.market_data.reconnect import ConnectionState, RealtimeConnectionState


RELIANCE = Instrument(symbol="RELIANCE", exchange="NSE")


def test_new_stream_is_fail_closed():
    state = RealtimeConnectionState()
    snapshot = state.snapshot(RELIANCE)
    assert snapshot.state == ConnectionState.DISCONNECTED
    assert snapshot.health == StreamHealth.DEGRADED
    assert state.can_publish_to_strategy(RELIANCE) is False


def test_connect_requires_resync_before_ready():
    state = RealtimeConnectionState()
    state.begin_connect(RELIANCE)
    state.connected(RELIANCE)
    assert state.snapshot(RELIANCE).state == ConnectionState.CONNECTED
    assert state.can_publish_to_strategy(RELIANCE) is False

    state.sequence_gap(RELIANCE)
    assert state.snapshot(RELIANCE).state == ConnectionState.RESYNC_REQUIRED
    assert state.can_publish_to_strategy(RELIANCE) is False

    state.resynced(RELIANCE, 100)
    assert state.snapshot(RELIANCE).state == ConnectionState.READY
    assert state.snapshot(RELIANCE).health == StreamHealth.HEALTHY
    assert state.can_publish_to_strategy(RELIANCE) is True


def test_disconnect_is_not_strategy_ready():
    state = RealtimeConnectionState()
    state.begin_connect(RELIANCE)
    state.connected(RELIANCE)
    state.resynced(RELIANCE, 100)
    state.disconnected(RELIANCE)
    assert state.snapshot(RELIANCE).state == ConnectionState.DISCONNECTED
    assert state.can_publish_to_strategy(RELIANCE) is False


def test_reconnect_attempts_increment():
    state = RealtimeConnectionState()
    state.begin_connect(RELIANCE)
    assert state.snapshot(RELIANCE).reconnect_attempts == 1
    state.disconnected(RELIANCE)
    state.begin_connect(RELIANCE)
    assert state.snapshot(RELIANCE).reconnect_attempts == 2


def test_resync_marks_tracker_healthy():
    state = RealtimeConnectionState()
    state.begin_connect(RELIANCE)
    state.connected(RELIANCE)
    state.sequence_gap(RELIANCE)
    state.resynced(RELIANCE, 200)
    assert state.can_publish_to_strategy(RELIANCE)
