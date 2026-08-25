from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter(prefix="/execution", tags=["execution"])


def _authorize(request: Request, token: str | None) -> None:
    if token != getattr(request.app.state, "execution_health_token", None):
        raise HTTPException(status_code=401, detail="execution alert authentication required")


@router.get("/alert-delivery-metrics")
def delivery_metrics(request: Request, x_execution_health_token: str | None = Header(default=None)) -> dict:
    _authorize(request, x_execution_health_token)
    store = getattr(request.app.state, "execution_alert_dead_letter_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="delivery metrics unavailable")
    metrics = store.metrics()
    return {"pending": metrics.pending, "delivered": metrics.delivered, "dead_lettered": metrics.dead_lettered, "total_attempts": metrics.total_attempts}
