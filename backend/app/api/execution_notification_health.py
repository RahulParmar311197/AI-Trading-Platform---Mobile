from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter(prefix="/execution", tags=["execution"])


@router.get("/notification-health")
def notification_health(request: Request, x_execution_health_token: str | None = Header(default=None)) -> dict:
    if x_execution_health_token != getattr(request.app.state, "execution_health_token", None):
        raise HTTPException(status_code=401, detail="execution notification authentication required")
    worker_health = getattr(request.app.state, "execution_alert_worker_health", None)
    delivery_store = getattr(request.app.state, "execution_alert_dead_letter_store", None)
    if worker_health is None or delivery_store is None:
        raise HTTPException(status_code=503, detail="notification health unavailable")
    worker = worker_health.snapshot()
    delivery = delivery_store.metrics()
    return {
        "status": "HEALTHY" if worker.status == "RUNNING" and worker.last_success_at else "DEGRADED",
        "worker": {
            "status": worker.status,
            "last_started_at": worker.last_started_at,
            "last_tick_at": worker.last_tick_at,
            "last_success_at": worker.last_success_at,
        },
        "delivery": {
            "pending": delivery.pending,
            "delivered": delivery.delivered,
            "dead_lettered": delivery.dead_lettered,
            "total_attempts": delivery.total_attempts,
            "failed_total": worker.failed_total,
        },
    }
