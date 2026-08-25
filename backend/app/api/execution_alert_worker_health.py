from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter(prefix="/execution", tags=["execution"])


@router.get("/alert-worker-health")
def worker_health(request: Request, x_execution_health_token: str | None = Header(default=None)) -> dict:
    if x_execution_health_token != getattr(request.app.state, "execution_health_token", None):
        raise HTTPException(status_code=401, detail="execution alert authentication required")
    health = getattr(request.app.state, "execution_alert_worker_health", None)
    if health is None:
        raise HTTPException(status_code=503, detail="worker health unavailable")
    snapshot = health.snapshot()
    return {"status": snapshot.status, "last_started_at": snapshot.last_started_at, "last_tick_at": snapshot.last_tick_at, "last_success_at": snapshot.last_success_at, "processed_total": snapshot.processed_total, "delivered_total": snapshot.delivered_total, "failed_total": snapshot.failed_total, "pending": snapshot.pending, "dead_lettered": snapshot.dead_lettered}
