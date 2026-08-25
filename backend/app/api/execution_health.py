from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from app.execution_health import ExecutionHealth
from app.execution_health_dto import ExecutionHealthDTO

router = APIRouter(prefix="/execution", tags=["execution"])


@router.get("/health")
def execution_health(request: Request, x_execution_health_token: str | None = Header(default=None)) -> dict:
    expected = getattr(request.app.state, "execution_health_token", None)
    if not expected or x_execution_health_token != expected:
        raise HTTPException(status_code=401, detail="execution health authentication required")
    observability = request.app.state.execution_observability
    return ExecutionHealthDTO.current(ExecutionHealth(observability))
