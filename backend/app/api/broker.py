from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.broker_adapter import BrokerOrder, PaperBrokerAdapter

router=APIRouter(prefix="/api/broker",tags=["broker"])
broker=PaperBrokerAdapter()
class SubmitRequest(BaseModel):
    symbol:str; side:str; quantity:float=Field(gt=0); order_type:str="MARKET"; price:float|None=None; stop:float|None=None; target:float|None=None
@router.get("/account")
def account(): return broker.get_account()
@router.get("/positions")
def positions(): return broker.get_positions()
@router.post("/orders")
def submit(p:SubmitRequest):
    try:return broker.submit_order(BrokerOrder(**p.model_dump()))
    except ValueError as e: raise HTTPException(422,str(e))
@router.get("/orders/{order_id}")
def get_order(order_id:str):
    try:return broker.get_order(order_id)
    except KeyError: raise HTTPException(404,"order not found")
@router.post("/orders/{order_id}/cancel")
def cancel(order_id:str):
    try:return broker.cancel_order(order_id)
    except KeyError: raise HTTPException(404,"order not found")
