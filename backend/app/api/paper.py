from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.schemas import OrderRequest
from app.risk.engine import RiskEngine
router=APIRouter(tags=["paper"])
engine=RiskEngine()
orders=[]

@router.post("/paper/orders")
def place_paper_order(order:OrderRequest):
    order=order.model_copy(update={"mode":"PAPER"})
    decision=engine.validate(order,__import__('app.schemas',fromlist=['RiskConfig']).RiskConfig(),100000,0,0,len(orders))
    if not decision.approved: raise HTTPException(409,detail={"status":"REJECTED","reasons":decision.reasons})
    record={"id":len(orders)+1,"status":"FILLED","created_at":datetime.now(timezone.utc).isoformat(),**order.model_dump()}
    orders.append(record); return record

@router.get("/paper/orders")
def list_paper_orders(): return orders
