from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.position_manager import PositionManager

router=APIRouter(prefix="/api/positions",tags=["positions"])
manager=PositionManager()
class OpenRequest(BaseModel):
    symbol:str; side:str; quantity:float=Field(gt=0); price:float=Field(gt=0); stop:float|None=None; target:float|None=None
class MarkRequest(BaseModel): price:float=Field(gt=0)
class ExitRequest(BaseModel): quantity:float=Field(gt=0); price:float=Field(gt=0)
class ReconcileRequest(BaseModel): broker_positions:list[dict]

def out(p): return p.__dict__.copy()
@router.post("")
def open_position(p:OpenRequest):
    try:return out(manager.open(p.symbol,p.side,p.quantity,p.price,p.stop,p.target))
    except ValueError as e:raise HTTPException(409,str(e))
@router.post("/{symbol}/mark")
def mark(symbol:str,p:MarkRequest):
    try:return out(manager.mark(symbol,p.price))
    except KeyError:raise HTTPException(404,"position not found")
@router.post("/{symbol}/exit")
def exit_position(symbol:str,p:ExitRequest):
    try:return out(manager.partial_exit(symbol,p.quantity,p.price))
    except (KeyError,ValueError) as e:raise HTTPException(409,str(e))
@router.post("/reconcile")
def reconcile(p:ReconcileRequest):return manager.reconcile(p.broker_positions)
