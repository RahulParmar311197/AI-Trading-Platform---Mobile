from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.paper_execution import paper_broker

router = APIRouter(prefix="/api/paper", tags=["paper-execution"])


class OpenRequest(BaseModel):
    symbol: str
    side: str = Field(pattern="^(BUY|SELL)$")
    quantity: float = Field(gt=0)
    entry: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    target: float = Field(gt=0)
    equity: float | None = Field(default=None, gt=0)
    max_risk_percent: float = Field(default=1.0, gt=0, le=10)
    max_daily_loss_percent: float = Field(default=3.0, gt=0, le=100)
    max_exposure_percent: float = Field(default=20.0, gt=0, le=100)
    max_positions: int = Field(default=5, ge=1, le=100)


class CloseRequest(BaseModel):
    position_id: str
    exit_price: float = Field(gt=0)
    exit_reason: str = "MANUAL"


@router.post("/positions", status_code=201)
def open_position(payload: OpenRequest):
    try:
        return paper_broker.open(**payload.model_dump()).__dict__
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/positions/close")
def close_position(payload: CloseRequest):
    try:
        return paper_broker.close(payload.position_id, payload.exit_price, payload.exit_reason).__dict__
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/positions")
def positions():
    return [p.__dict__ for p in paper_broker.list()]


@router.get("/positions/{position_id}/mark")
def mark_position(position_id: str, price: float):
    try:
        return paper_broker.mark(position_id, price)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
