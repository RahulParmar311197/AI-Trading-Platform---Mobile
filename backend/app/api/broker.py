from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from app.broker_adapter import BrokerOrderRequest

router=APIRouter(prefix="/api/broker",tags=["broker"])
class SubmitRequest(BaseModel):
    client_order_id:str=Field(min_length=1,max_length=128); symbol:str; side:str; quantity:float=Field(gt=0); order_type:str="MARKET"; price:float|None=None; stop:float|None=None; target:float|None=None

def _resources(request:Request):
    resources=getattr(request.app.state,"resources",None)
    if resources is None: raise HTTPException(503,"execution resources unavailable")
    return resources

@router.get("/account")
def account(request:Request): return request.app.state.broker_router.get_account()
@router.get("/positions")
def positions(request:Request): return request.app.state.broker_router.get_positions()

@router.post("/orders")
def submit(p:SubmitRequest,request:Request):
    resources=_resources(request)
    startup=getattr(request.app.state,"startup_recovery",None)
    if startup is None or getattr(startup,"state",None).value != "READY": raise HTTPException(409,"STARTUP_EXECUTION_NOT_READY")
    order=BrokerOrderRequest(client_order_id=p.client_order_id,symbol=p.symbol.upper(),side=p.side.upper(),quantity=p.quantity,order_type=p.order_type,price=p.price,stop=p.stop,target=p.target)
    decision=resources.authorization.check(order)
    if not decision.allowed: raise HTTPException(409,{"code":decision.code,"reason":decision.reason})
    try:return request.app.state.broker_router.submit(order)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    except RuntimeError as exc: raise HTTPException(409,str(exc)) from exc

@router.get("/orders/{order_id}")
def get_order(order_id:str,request:Request):
    try:return request.app.state.broker_router.get_order(order_id)
    except KeyError: raise HTTPException(404,"order not found")

@router.post("/orders/{order_id}/cancel")
def cancel(order_id:str,request:Request):
    try:return request.app.state.broker_router.cancel(order_id)
    except KeyError: raise HTTPException(404,"order not found")
