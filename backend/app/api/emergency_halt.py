from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.auth.security import decode_access_token
from app.core.config import settings

router = APIRouter(prefix="/api/emergency", tags=["emergency"])
security = HTTPBearer(auto_error=False)


class HaltRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


def _controller():
    from app.main import emergency_halt_controller
    return emergency_halt_controller


def _require_admin(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str:
    if not settings.recovery_admin_username:
        raise HTTPException(503, "recovery admin is not configured")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "bearer authentication required")
    try:
        payload = decode_access_token(credentials.credentials)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(401, "invalid authentication token")
    if payload.get("sub") != settings.recovery_admin_username:
        raise HTTPException(403, "recovery admin access required")
    return str(payload.get("sub"))


@router.get("/status")
def status():
    controller = _controller()
    state = controller.safety_store.load()
    return {"halted": state.trading_halted, "reason": state.halt_reason}


@router.post("/halt")
def halt(request: HaltRequest, _: str = Depends(_require_admin)):
    controller = _controller()
    try:
        result = controller.halt(request.reason)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc))
    return {"halted": result.halted, "reason": result.reason, "timestamp": result.timestamp.isoformat()}


@router.post("/clear")
def clear(_: str = Depends(_require_admin)):
    controller = _controller()
    try:
        controller.clear()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    return {"halted": controller.is_halted(), "startup_state": controller.startup_state.state.value}
