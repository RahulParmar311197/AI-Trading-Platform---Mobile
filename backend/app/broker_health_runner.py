from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.broker_adapter import BrokerHealth
from app.broker_connectivity_registry import BrokerConnectivityRegistry


@dataclass(frozen=True)
class HealthCheckResult:
    broker_account_id: int
    broker_route: str
    healthy: bool
    message: str


class BrokerHealthRunner:
    """Synchronously applies provider health results to route-scoped supervisors.

    Scheduling is deliberately owned by the application lifecycle/worker layer;
    this class performs one deterministic check and never places orders.
    """

    def __init__(self, registry: BrokerConnectivityRegistry) -> None:
        self.registry = registry

    def check(
        self,
        *,
        broker_account_id: int,
        broker_route: str,
        health_provider: Callable[[], BrokerHealth | dict[str, Any]],
    ) -> HealthCheckResult:
        supervisor = self.registry.get(broker_account_id, broker_route)
        try:
            raw = health_provider()
            health = raw if isinstance(raw, BrokerHealth) else BrokerHealth(
                broker=str(raw.get("broker", broker_route)),
                healthy=bool(raw.get("healthy", raw.get("authenticated", False))),
                authenticated=bool(raw.get("authenticated", False)),
                live_trading_enabled=bool(raw.get("live_trading_enabled", False)),
                message=str(raw.get("message", "")),
            )
            # Authentication/health is required; a configured-but-disabled broker
            # must remain unavailable for live execution.
            healthy = health.healthy and health.authenticated
            if healthy:
                supervisor.record_success()
            else:
                supervisor.record_failure()
            return HealthCheckResult(broker_account_id, broker_route, healthy, health.message)
        except Exception as exc:
            supervisor.record_failure()
            return HealthCheckResult(broker_account_id, broker_route, False, f"health check failed: {exc}")
