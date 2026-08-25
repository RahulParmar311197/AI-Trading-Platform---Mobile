from __future__ import annotations

from dataclasses import asdict
from fastapi import APIRouter

from app.operational_metrics import TradingMetricsCollector
from app.system_health import TradingSystemHealth


def create_operational_router(health: TradingSystemHealth | None = None, metrics: TradingMetricsCollector | None = None) -> APIRouter:
    health = health or TradingSystemHealth()
    metrics = metrics or TradingMetricsCollector()
    router = APIRouter(tags=["operations"])

    @router.get("/health/live")
    def live() -> dict:
        return {"status": "ok", "live": health.liveness()}

    @router.get("/health/ready")
    def ready() -> dict:
        is_ready = health.readiness()
        return {"status": "ready" if is_ready else "not_ready", "ready": is_ready, "health": health.snapshot()}

    @router.get("/health")
    def health_status() -> dict:
        return health.snapshot()

    @router.get("/metrics/trading")
    def trading_metrics() -> dict:
        return metrics.snapshot()

    @router.get("/execution/status")
    def execution_status() -> dict:
        return {"health": health.snapshot(), "metrics": metrics.snapshot()}

    return router
