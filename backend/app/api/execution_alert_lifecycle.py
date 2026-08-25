from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter(prefix="/execution/alerts", tags=["execution"])


def _store(request: Request):
    store = getattr(request.app.state, "execution_alert_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="execution alert store unavailable")
    return store


def _authorize(request: Request, token: str | None) -> None:
    expected = getattr(request.app.state, "execution_health_token", None)
    if not expected or token != expected:
        raise HTTPException(status_code=401, detail="execution alert authentication required")


def _serialize(record) -> dict:
    return {
        "alert_id": record.alert_id,
        "created_at": record.created_at,
        "severity": record.severity,
        "reason_codes": list(record.reason_codes),
        "fingerprint": record.fingerprint,
        "status": record.status,
        "acknowledged_at": record.acknowledged_at,
        "resolved_at": record.resolved_at,
    }


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(request: Request, alert_id: int, x_execution_health_token: str | None = Header(default=None)):
    _authorize(request, x_execution_health_token)
    try:
        return _serialize(_store(request).acknowledge(alert_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="execution alert not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{alert_id}/resolve")
def resolve_alert(request: Request, alert_id: int, x_execution_health_token: str | None = Header(default=None)):
    _authorize(request, x_execution_health_token)
    try:
        return _serialize(_store(request).resolve(alert_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="execution alert not found") from exc
