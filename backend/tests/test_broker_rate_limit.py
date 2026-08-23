import asyncio

import pytest

from app.broker_rate_limit import AsyncRateLimiter, RateLimit, RetryPolicy


@pytest.mark.asyncio
async def test_rate_limit_allows_configured_burst():
    limiter = AsyncRateLimiter(RateLimit(2, 60))
    await limiter.acquire()
    await limiter.acquire()
    assert len(limiter._events) == 2


@pytest.mark.asyncio
async def test_retry_policy_retries_transient_failure():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary")
        return "ok"

    result = await RetryPolicy(max_attempts=3, base_delay=0).run(operation, lambda exc: True)
    assert result == "ok"
    assert attempts == 3


@pytest.mark.asyncio
async def test_retry_policy_does_not_retry_permanent_failure():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        raise ValueError("bad request")

    with pytest.raises(ValueError):
        await RetryPolicy(max_attempts=3, base_delay=0).run(operation, lambda exc: False)
    assert attempts == 1


def test_invalid_limits_are_rejected():
    with pytest.raises(ValueError):
        RateLimit(0, 1)
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
