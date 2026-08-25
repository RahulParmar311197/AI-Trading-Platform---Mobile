from __future__ import annotations

import sqlite3
from fastapi import APIRouter, Header, HTTPException, Query, Request

router = APIRouter(prefix="/execution", tags=["execution"])


def _authorize(request: Request, token: str | None) -> None:
    expected = getattr(request.app.state, "execution_health_token", None)
    if not expected or token != expected:
        raise HTTPException(status_code=401, detail="execution alert authentication required")


@router.get("/alert-events")
def alert_events(request: Request, x_execution_health_token: str | None = Header(default=None), limit: int = Query(default=50, ge=1, le=200)) -> dict:
    _authorize(request, x_execution_health_token)
    store = getattr(request.app.state, "execution_alert_event_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="execution alert event store unavailable")
    safe_limit = min(max(limit, 1), 200)
    with sqlite3.connect(store.path) as conn:
        rows = conn.execute("SELECT id,alert_id,event_type,created_at FROM execution_alert_events ORDER BY id DESC LIMIT ?", (safe_limit,)).fetchall()
    return {"events": [{"event_id": int(r[0]), "alert_id": int(r[1]), "event_type": str(r[2]), "created_at": str(r[3])} for r in rows]}
