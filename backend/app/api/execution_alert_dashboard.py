from __future__ import annotations

from collections import Counter
from datetime import datetime
from fastapi import APIRouter, Header, HTTPException, Query, Request

router = APIRouter(prefix="/execution", tags=["execution"])


def _authorize(request: Request, token: str | None) -> None:
    expected = getattr(request.app.state, "execution_health_token", None)
    if not expected or token != expected: raise HTTPException(status_code=401, detail="execution alert authentication required")


def _serialize(record) -> dict:
    return {"alert_id": record.alert_id, "created_at": record.created_at, "severity": record.severity, "reason_codes": list(record.reason_codes), "fingerprint": record.fingerprint, "status": record.status, "acknowledged_at": record.acknowledged_at, "resolved_at": record.resolved_at}


@router.get("/alert-dashboard")
def alert_dashboard(request: Request, x_execution_health_token: str | None = Header(default=None), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), severity: str | None = Query(default=None), status: str | None = Query(default=None), reason_code: str | None = Query(default=None), created_after: datetime | None = Query(default=None), created_before: datetime | None = Query(default=None)) -> dict:
    _authorize(request, x_execution_health_token)
    store = getattr(request.app.state, "execution_alert_store", None)
    if store is None: raise HTTPException(status_code=503, detail="execution alert store unavailable")
    page = store.query(limit=limit, offset=offset, severity=severity, status=status, reason_code=reason_code, created_after=created_after, created_before=created_before)
    active = [record for record in page.records if record.status in {"OPEN", "ACKNOWLEDGED"}]
    severity_counts = Counter(record.severity for record in active)
    status_counts = Counter(record.status for record in page.records)
    return {"total": page.total, "limit": page.limit, "offset": page.offset, "has_more": page.offset + len(page.records) < page.total, "active_count": len(active), "open_count": status_counts.get("OPEN", 0), "acknowledged_count": status_counts.get("ACKNOWLEDGED", 0), "resolved_count": status_counts.get("RESOLVED", 0), "severity_counts": dict(severity_counts), "latest_incident": _serialize(page.records[0]) if page.records else None, "active_incidents": [_serialize(record) for record in active], "recovery_state": "RECOVERED" if not active else "INCIDENT_ACTIVE", "filters": {"severity": severity, "status": status, "reason_code": reason_code, "created_after": created_after.isoformat() if created_after else None, "created_before": created_before.isoformat() if created_before else None}}
