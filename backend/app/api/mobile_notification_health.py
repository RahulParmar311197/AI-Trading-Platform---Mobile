from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.authorization import NotificationHealthAuthorization
from app.auth.dependencies import current_user
from app.auth.session import UserSession
from app.execution_notification_health_policy import NotificationHealthPolicy

router = APIRouter(prefix="/mobile/execution", tags=["mobile-execution"])


@router.get("/notification-health")
def mobile_notification_health(request: Request, session: UserSession = Depends(current_user)) -> dict:
    if not NotificationHealthAuthorization.can_read_health(session):
        raise HTTPException(status_code=403, detail="notification health access denied")
    worker_health = getattr(request.app.state, "execution_alert_worker_health", None)
    delivery_store = getattr(request.app.state, "execution_alert_dead_letter_store", None)
    if worker_health is None or delivery_store is None:
        raise HTTPException(status_code=503, detail="notification health unavailable")
    worker = worker_health.snapshot()
    delivery = delivery_store.metrics()
    policy = NotificationHealthPolicy()
    status, reasons = policy.evaluate(worker.status, worker.last_success_at, delivery.pending, delivery.dead_lettered)
    return {
        "status": status,
        "reasons": reasons,
        "worker_status": worker.status,
        "pending": delivery.pending,
        "delivered": delivery.delivered,
        "dead_lettered": delivery.dead_lettered,
        "failed_total": worker.failed_total,
        "last_success_at": worker.last_success_at,
    }
