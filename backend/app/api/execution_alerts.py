from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, Request

from app.execution_alert_store import ExecutionAlertStore

router = APIRouter(prefix="/execution", tags=["execution"])


@router.get("/alerts")
def execution_alerts(
    request: Request,
    x_execution_health_token: str | None = Header(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    expected = getattr(request.app.state, "execution_health_token", None)
    if not expected or x_execution_health_token != expected:
        raise HTTPException(status_code=401, detail="execution alert authentication required")
    store = getattr(request.app.state, "execution_alert_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="execution alert store unavailable")
    return [
        {
            "alert_id": record.alert_id,
            "created_at": record.created_at,
            "severity": record.severity,
            "reason_codes": list(record.reason_codes),
            "fingerprint": record.fingerprint,
        }
        for record in store.recent(limit)
    ]
