from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from app.execution_notification_health_policy import NotificationHealthPolicy

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
    policy = NotificationHealthPolicy(
        stale_after_seconds=int(getattr(request.app.state, "notification_health_stale_seconds", 30)),
        pending_threshold=int(getattr(request.app.state, "notification_health_pending_threshold", 100)),
        dead_letter_threshold=int(getattr(request.app.state, "notification_health_dead_letter_threshold", 1)),
    )
    status, reasons = policy.evaluate(worker.status, worker.last_success_at, delivery.pending, delivery.dead_lettered)
    return {
        "status": status,
        "reasons": reasons,
        "worker": {"status": worker.status, "last_started_at": worker.last_started_at, "last_tick_at": worker.last_tick_at, "last_success_at": worker.last_success_at},
        "delivery": {"pending": delivery.pending, "delivered": delivery.delivered, "dead_lettered": delivery.dead_lettered, "total_attempts": delivery.total_attempts, "failed_total": worker.failed_total},
        "thresholds": {"stale_after_seconds": policy.stale_after_seconds, "pending_threshold": policy.pending_threshold, "dead_letter_threshold": policy.dead_letter_threshold},
    }
