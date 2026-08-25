from app.operational_api import create_operational_router
from app.operational_metrics import TradingMetricsCollector
from app.system_health import TradingSystemHealth


def test_health_snapshot_does_not_deadlock_and_reports_readiness():
    health = TradingSystemHealth()
    health.record("broker_recovery", True, "ready")

    snapshot = health.snapshot()

    assert snapshot["ready"] is True
    assert snapshot["checks"]["broker_recovery"]["healthy"] is True


def test_operational_router_uses_injected_health_and_metrics():
    health = TradingSystemHealth()
    metrics = TradingMetricsCollector()
    health.record("risk_readiness", False, "blocked")
    metrics.increment("reconciliation_failures")

    router = create_operational_router(health, metrics)
    paths = {route.path for route in router.routes}

    assert "/health/live" in paths
    assert "/health/ready" in paths
    assert "/health" in paths
    assert "/metrics/trading" in paths
    assert "/execution/status" in paths

    ready_route = next(route for route in router.routes if route.path == "/health/ready")
    result = ready_route.endpoint()
    assert result["status"] == "not_ready"
    assert result["ready"] is False
