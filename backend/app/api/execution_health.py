from __future__ import annotations

from fastapi import APIRouter, Request

from app.execution_health import ExecutionHealth
from app.execution_health_dto import ExecutionHealthDTO

router = APIRouter(prefix="/execution", tags=["execution"])


@router.get("/health")
def execution_health(request: Request) -> dict:
    observability = request.app.state.execution_observability
    return ExecutionHealthDTO.current(ExecutionHealth(observability))
