from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router=APIRouter(prefix="/api/broker",tags=["broker"])

class SubmitRequest(BaseModel):
    client_order_id:str=Field(min_length=1,max_length=128)
    symbol:str
    side:str
    quantity:float=Field(gt=0)
    order_type:str="MARKET"
    price:float|None=None
    stop:float|None=None
    target:float|None=None


def _resources(request:Request):
    resources=getattr(request.app.state,"resources",None)
    if resources is None: raise HTTPException(503,"execution resources unavailable")
    return resources


@router.get("/account")
def account(request:Request):
    return request.app.state.broker_router.get_account()


@router.get("/positions")
def positions(request:Request):
    return request.app.state.broker_router.get_positions()


@router.post("/orders")
def submit(_:SubmitRequest,request:Request):
    _resources(request)
    raise HTTPException(410,"DIRECT_BROKER_SUBMISSION_DISABLED: use POST /api/orders")


@router.get("/orders/{order_id}")
def get_order(order_id:str,request:Request):
    try:return request.app.state.broker_router.get_order(order_id)
    except KeyError: raise HTTPException(404,"order not found")


@router.post("/orders/{order_id}/cancel")
def cancel(order_id:str,request:Request):
    try:return request.app.state.broker_router.cancel(order_id)
    except KeyError: raise HTTPException(404,"order not found")
