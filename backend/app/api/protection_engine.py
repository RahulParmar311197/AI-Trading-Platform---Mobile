from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.protection_engine import ProtectionConfig, evaluate

router=APIRouter(prefix="/api/protection",tags=["protection"])
class ProtectionRequest(BaseModel):
    side:str; entry:float=Field(gt=0); current:float=Field(gt=0); stop:float=Field(gt=0); quantity:float=Field(gt=0)
    breakeven_trigger_r:float=Field(default=1.0,gt=0); trailing_trigger_r:float=Field(default=1.5,gt=0); trailing_distance_r:float=Field(default=1.0,gt=0); partial_trigger_r:float=Field(default=2.0,gt=0); partial_exit_pct:float=Field(default=0.5,gt=0,le=1)
@router.post("/evaluate")
def protection(p:ProtectionRequest):
    try:
        cfg=ProtectionConfig(p.breakeven_trigger_r,0.0002,p.trailing_trigger_r,p.trailing_distance_r,p.partial_trigger_r,p.partial_exit_pct)
        return evaluate(side=p.side,entry=p.entry,current=p.current,stop=p.stop,quantity=p.quantity,config=cfg).__dict__
    except ValueError as e: raise HTTPException(422,str(e))
