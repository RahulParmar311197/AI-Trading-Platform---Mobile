from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from app.backtest_service import BacktestService
from app.backtest_result_schema import BacktestRunResponse
router=APIRouter(prefix='/api/v1/backtests',tags=['backtests'])
class RunRequest(BaseModel):
 symbol:str=Field(min_length=1); timeframe:str=Field(min_length=1); start:datetime; end:datetime; initial_equity:float=Field(gt=0); risk_pct:float=Field(gt=0,le=100); data_root:str=Field(min_length=1)
@router.post('/run',response_model=BacktestRunResponse)
def run(req:RunRequest):
 if req.start>=req.end: raise HTTPException(422,'start must be before end')
 if req.start.tzinfo is None or req.end.tzinfo is None: raise HTTPException(422,'timestamps must include timezone')
 try: return BacktestService(req.data_root).run(req.symbol,req.timeframe,req.start,req.end,req.initial_equity,req.risk_pct)
 except (ValueError,FileNotFoundError) as e: raise HTTPException(422,str(e))
