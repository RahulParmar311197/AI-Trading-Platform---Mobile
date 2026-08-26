from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.broker_connectivity_registry import BrokerConnectivityRegistry
from app.broker_health_runner import BrokerHealthRunner, HealthCheckResult
from app.broker_router import BrokerRouter


@dataclass(frozen=True)
class BrokerHealthWorkerConfig:
    interval_seconds: float = 15.0


class BrokerHealthWorker:
    """Periodic route-scoped broker health worker; never submits orders."""

    def __init__(self, router: BrokerRouter, registry: BrokerConnectivityRegistry, config: BrokerHealthWorkerConfig | None = None) -> None:
        self.router = router
        self.runner = BrokerHealthRunner(registry)
        self.config = config or BrokerHealthWorkerConfig()
        if self.config.interval_seconds <= 0:
            raise ValueError("broker health interval must be greater than zero")

    def run_once(self) -> list[HealthCheckResult]:
        results: list[HealthCheckResult] = []
        for route in list(self.router.routes.values()):
            if route.broker_account_id is None or not route.enabled:
                continue
            health = getattr(route.adapter, "health", None)
            if health is None:
                continue
            results.append(self.runner.check(broker_account_id=int(route.broker_account_id), broker_route=route.name, health_provider=health))
        return results

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            self.run_once()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.config.interval_seconds)
            except asyncio.TimeoutError:
                continue
