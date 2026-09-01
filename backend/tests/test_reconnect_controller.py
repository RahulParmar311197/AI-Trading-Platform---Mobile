import pytest

from app.market_data.reconnect_controller import BackoffPolicy, ReconnectController


@pytest.mark.asyncio
async def test_reconnect_stops_after_max_attempts():
    calls = []
    sleeps = []

    def connect():
        calls.append(1)
        return False

    async def sleep(delay):
        sleeps.append(delay)

    controller = ReconnectController(
        connect,
        policy=BackoffPolicy(initial_seconds=0.01, max_seconds=0.01, jitter_ratio=0),
        sleep=sleep,
        max_attempts=3,
    )

    assert await controller.run() is False
    assert controller.attempts == 3
    assert len(calls) == 3
    assert len(sleeps) == 2


def test_reconnect_rejects_invalid_max_attempts():
    with pytest.raises(ValueError):
        ReconnectController(lambda: True, max_attempts=0)


@pytest.mark.asyncio
async def test_reconnect_succeeds_before_limit_without_extra_sleep():
    calls = []
    sleeps = []

    def connect():
        calls.append(1)
        return len(calls) == 2

    async def sleep(delay):
        sleeps.append(delay)

    controller = ReconnectController(
        connect,
        policy=BackoffPolicy(initial_seconds=0.01, max_seconds=0.01, jitter_ratio=0),
        sleep=sleep,
        max_attempts=5,
    )

    assert await controller.run() is True
    assert controller.attempts == 2
    assert len(calls) == 2
    assert len(sleeps) == 1
