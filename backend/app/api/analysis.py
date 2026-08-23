from fastapi import APIRouter
from pydantic import BaseModel, Field

router=APIRouter(tags=["ai"])
class StrategyPrompt(BaseModel):
    prompt:str=Field(min_length=5,max_length=4000)

@router.post("/ai/strategy")
def build_strategy(body:StrategyPrompt):
    text=body.prompt.lower()
    conditions=[]
    if "liquidity" in text or "sweep" in text: conditions.append("liquidity_sweep")
    if "mss" in text or "choch" in text: conditions.append("mss")
    if "fvg" in text: conditions.append("fvg")
    if "order block" in text or "ob" in text: conditions.append("order_block")
    direction="bullish" if "bull" in text or "long" in text else "bearish" if "bear" in text or "short" in text else "neutral"
    return {"direction":direction,"conditions":conditions,"entry":"fvg_retest" if "fvg" in conditions else "confirmation","risk":{"max_risk_percent":0.5},"minimum_rr":2,"validated":True}

@router.post("/ai/analyze")
def analyze_context(context:dict):
    bias=context.get("bias","NEUTRAL")
    return {"bias":bias,"setup_score":context.get("score",0),"explanation":"Structured market context received. Deterministic engines remain authoritative for execution.","risk_note":"This is analysis, not a guarantee of outcome."}
