import asyncio

from app.broker_adapter import BrokerHealth
from app.broker_connectivity_registry import BrokerConnectivityRegistry
from app.broker_health_worker import BrokerHealthWorker, BrokerHealthWorkerConfig


class FakeRoute:
    def __init__(self, account_id, name, enabled, health):
        self.broker_account_id = account_id
        self.name = name
        self.enabled = enabled
        self.adapter = type("Adapter", (), {"health": health})()


class FakeRouter:
    def __init__(self, routes):
        self.routes = routes


def test_run_once_updates_route_state_and_skips_disabled_or_unbound():
    def healthy():
        return BrokerHealth("fake", True, True, True, "ok")

    routes = {
        "healthy": FakeRoute(1, "healthy", True, healthy),
        "disabled": FakeRoute(2, "disabled", False, healthy),
        "unbound": FakeRoute(None, "unbound", True, healthy),
    }
    registry = BrokerConnectivityRegistry()
    worker = BrokerHealthWorker(FakeRouter(routes), registry)

    results = worker.run_once()

    assert len(results) == 1
    assert registry.get(1, "healthy").snapshot().can_trade is True
    assert registry.get(2, "disabled").snapshot().can_trade is False


def test_health_exception_isolated_and_route_fails_closed():
    def broken():
        raise RuntimeError("network down")

    worker = BrokerHealthWorker(
        FakeRouter({"broken": FakeRoute(7, "broken", True, broken)}),
        BrokerConnectivityRegistry(),
    )

    result = worker.run_once()[0]
    assert result.healthy is False
    assert "network down" in result.message


def test_worker_stops_cleanly():
    calls = []

    def healthy():
        calls.append(1)
        return BrokerHealth("fake", True, True, True, "ok")

    async def scenario():
        worker = BrokerHealthWorker(
            FakeRouter({"route": FakeRoute(1, "route", True, healthy)}),
            BrokerConnectivityRegistry(),
            BrokerHealthWorkerConfig(interval_seconds=0.01),
        )
        stop = asyncio.Event()
        task = asyncio.create_task(worker.run(stop))
        await asyncio.sleep(0.02)
        stop.set()
        await asyncio.wait_for(task, timeout=1)
        assert calls

    asyncio.run(scenario())
