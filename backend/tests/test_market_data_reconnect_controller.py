import random

import pytest

from app.market_data.reconnect_controller import BackoffPolicy, ReconnectController


def test_backoff_is_exponential_and_bounded():
    policy = BackoffPolicy(initial_seconds=1, max_seconds=5, multiplier=2, jitter_ratio=0)
    assert policy.delay(1) == 1
    assert policy.delay(2) == 2
    assert policy.delay(3) == 4
    assert policy.delay(4) == 5


def test_jitter_stays_within_expected_bounds():
    policy = BackoffPolicy(initial_seconds=10, max_seconds=100, multiplier=2, jitter_ratio=0.2)
    rng = random.Random(7)
    delay = policy.delay(2, rng=rng)
    assert 16 <= delay <= 24


@pytest.mark.asyncio
async def test_reconnect_retries_until_success():
    attempts = []
    sleeps = []

    def connect():
        attempts.append(1)
        return len(attempts) == 3

    async def sleep(seconds):
        sleeps.append(seconds)

    controller = ReconnectController(
        connect,
        policy=BackoffPolicy(initial_seconds=1, max_seconds=10, jitter_ratio=0),
        sleep=sleep,
    )
    assert await controller.run() is True
    assert controller.attempts == 3
    assert sleeps == [1, 2]


@pytest.mark.asyncio
async def test_stop_ends_failed_reconnect_loop():
    controller = None
    calls = []

    def connect():
        calls.append(1)
        controller.stop()
        return False

    async def sleep(_):
        pass

    controller = ReconnectController(connect, sleep=sleep)
    assert await controller.run() is False
    assert calls == [1]


def test_invalid_attempt_is_rejected():
    with pytest.raises(ValueError):
        BackoffPolicy().delay(0)
