from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.broker_adapter import BrokerOrderRequest
from app.db import get_db
from app.models import Order
from app.safety_state import SafetyStateStore

router = APIRouter(prefix="/api/orders", tags=["orders"])


class OrderRequest(BaseModel):
    user_id: int = Field(gt=0)
    symbol: str = Field(min_length=1, max_length=64)
    side: str = Field(pattern="^(BUY|SELL)$")
    quantity: float = Field(gt=0)
    order_type: str = Field(default="MARKET", pattern="^(MARKET|LIMIT|SL)$")


def require_trading_ready(request: Request) -> None:
    safety_store = getattr(request.app.state, "resources", None)
    safety_store = safety_store.safety_store if safety_store else SafetyStateStore()
    state = safety_store.load()
    if state.trading_halted:
        raise HTTPException(status_code=409, detail={"code": "TRADING_HALTED", "reason": state.halt_reason})


@router.post("", status_code=201)
def create_order(
    payload: OrderRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_trading_ready),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    from app.main import broker_router, execution_store, idempotency_store
    from app.order_execution_service import OrderExecutionService
    from app.order_lifecycle import OrderLifecycle

    resources = getattr(request.app.state, "resources", None)
    if resources is not None:
        broker_router = request.app.state.broker_router
        execution_store = resources.execution_store
        idempotency_store = resources.idempotency_store

    client_order_id = idempotency_key.strip() if idempotency_key else str(uuid.uuid4())
    if not client_order_id or len(client_order_id) > 128:
        raise HTTPException(status_code=422, detail="Idempotency-Key must be at most 128 characters")

    existing = db.query(Order).filter(Order.client_order_id == client_order_id).first()
    if existing is not None:
        return {"id": existing.id, "client_order_id": existing.client_order_id, "broker_order_id": existing.broker_order_id, "status": existing.status, "message": "IDEMPOTENT_REPLAY"}

    symbol = payload.symbol.upper()
    order = Order(user_id=payload.user_id, client_order_id=client_order_id, symbol=symbol, side=payload.side, quantity=payload.quantity, order_type=payload.order_type, status="PENDING")
    db.add(order)
    db.flush()

    lifecycle = OrderLifecycle()
    execution_store.load(lifecycle)
    service = OrderExecutionService(broker_router, lifecycle, execution_store, idempotency_store)
    result = service.submit(BrokerOrderRequest(client_order_id=client_order_id, symbol=symbol, side=payload.side, quantity=payload.quantity, order_type=payload.order_type))

    order.status = result.status
    order.broker_order_id = result.broker_order_id
    if result.message:
        order.note = result.message
    db.commit()
    db.refresh(order)
    return {"id": order.id, "client_order_id": order.client_order_id, "broker_order_id": order.broker_order_id, "status": order.status, "message": result.message}
