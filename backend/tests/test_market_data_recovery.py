import pytest

from app.market_data.reconnect_controller import BackoffPolicy, ReconnectController, ReconnectRecovery


@pytest.mark.asyncio
async def test_recovery_requires_connect_then_resync():
    events = []
    async def connect():
        events.append("connect")
        return True
    async def resync():
        events.append("resync")
        return True
    controller = ReconnectController(connect, policy=BackoffPolicy(jitter_ratio=0))
    recovery = ReconnectRecovery(controller, resync)
    assert await recovery.recover() is True
    assert events == ["connect", "resync"]


@pytest.mark.asyncio
async def test_failed_resync_does_not_report_recovered():
    async def connect():
        return True
    async def resync():
        return False
    recovery = ReconnectRecovery(ReconnectController(connect), resync)
    assert await recovery.recover() is False


@pytest.mark.asyncio
async def test_resync_exception_is_fail_closed():
    async def connect():
        return True
    async def resync():
        raise RuntimeError("historical source unavailable")
    recovery = ReconnectRecovery(ReconnectController(connect), resync)
    assert await recovery.recover() is False
