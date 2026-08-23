from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.execution_lifecycle import ExecutionLedger, OrderStatus

router = APIRouter(prefix="/api/execution", tags=["execution"])
ledger = ExecutionLedger()

class OrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: float = Field(gt=0)
    stop: float | None = Field(default=None, gt=0)
    target: float | None = Field(default=None, gt=0)
    client_order_id: str | None = None

class FillRequest(BaseModel):
    price: float = Field(gt=0)
    quantity: float = Field(gt=0)

@router.post("/orders")
def create_order(p: OrderRequest):
    try: return ledger.create(p.symbol,p.side,p.quantity,p.stop,p.target,p.client_order_id).__dict__
    except ValueError as e: raise HTTPException(status_code=409, detail=str(e))

@router.post("/orders/{order_id}/risk-approve")
def approve(order_id: str):
    try: return ledger.transition(order_id, OrderStatus.RISK_APPROVED).__dict__
    except (KeyError,ValueError) as e: raise HTTPException(status_code=409, detail=str(e))

@router.post("/orders/{order_id}/submit")
def submit(order_id: str):
    try: return ledger.transition(order_id, OrderStatus.SUBMITTED).__dict__
    except (KeyError,ValueError) as e: raise HTTPException(status_code=409, detail=str(e))

@router.post("/orders/{order_id}/fill")
def fill(order_id: str, p: FillRequest):
    try: return ledger.fill(order_id,p.price,p.quantity).__dict__
    except (KeyError,ValueError) as e: raise HTTPException(status_code=409, detail=str(e))

@router.post("/orders/{order_id}/close")
def close(order_id: str):
    try: return ledger.transition(order_id, OrderStatus.CLOSED).__dict__
    except (KeyError,ValueError) as e: raise HTTPException(status_code=409, detail=str(e))
