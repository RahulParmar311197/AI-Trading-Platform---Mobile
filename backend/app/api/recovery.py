import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.security import decode_access_token
from app.core.config import settings

router = APIRouter(prefix="/api/recovery", tags=["recovery"])
security = HTTPBearer(auto_error=False)


def _manager():
    # Lazy import avoids an app.main <-> api.recovery import cycle.
    from app.main import recovery_manager

    return recovery_manager


def _require_recovery_admin(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str:
    if not settings.recovery_admin_username:
        raise HTTPException(503, "recovery admin is not configured")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "bearer authentication required")
    try:
        payload = decode_access_token(credentials.credentials)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(401, "invalid authentication token")
    subject = payload.get("sub")
    if subject != settings.recovery_admin_username:
        raise HTTPException(403, "recovery admin access required")
    return subject


def _status_payload():
    manager = _manager()
    state = manager.safety_store.load()
    return {
        "trading_halted": manager.trading_halted or state.trading_halted,
        "halt_reason": state.halt_reason,
        "last_reconciliation_at": state.last_reconciliation_at.isoformat() if state.last_reconciliation_at else None,
        "recovery_manager": "ready",
    }


@router.get("/status")
def status():
    return _status_payload()


@router.post("/resume")
def resume(_: str = Depends(_require_recovery_admin)):
    manager = _manager()
    try:
        result = manager.resume_after_verified_reconciliation()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    return {
        "ready": result.ready,
        "reason": result.reason,
        "trading_halted": manager.trading_halted,
    }
