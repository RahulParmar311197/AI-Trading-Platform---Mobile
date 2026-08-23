from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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


def require_trading_ready() -> None:
    state = SafetyStateStore().load()
    if state.trading_halted:
        raise HTTPException(status_code=409, detail={"code": "TRADING_HALTED", "reason": state.halt_reason})


@router.post("", status_code=201)
def create_order(payload: OrderRequest, db: Session = Depends(get_db), _: None = Depends(require_trading_ready)):
    import uuid
    order = Order(
        user_id=payload.user_id,
        client_order_id=str(uuid.uuid4()),
        symbol=payload.symbol.upper(),
        side=payload.side,
        quantity=payload.quantity,
        order_type=payload.order_type,
        status="PENDING",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"id": order.id, "client_order_id": order.client_order_id, "status": order.status}


@router.get("/{user_id}")
def list_orders(user_id: int, db: Session = Depends(get_db)):
    return db.query(Order).filter(Order.user_id == user_id).order_by(Order.id.desc()).all()
