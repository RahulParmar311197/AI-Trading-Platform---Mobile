from __future__ import annotations
from dataclasses import asdict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.backtest_analytics import BacktestAnalyticsEngine

router=APIRouter(prefix='/api/v1/backtests',tags=['backtests'])

class BacktestRequest(BaseModel):
    initial_equity:float=Field(gt=0)
    equity_curve:list[float]=Field(min_length=1)
    trade_pnls:list[float]=[]
    periods_per_year:float=Field(default=252,gt=0)

@router.post('/analytics')
def analytics(req:BacktestRequest):
    try:
        return asdict(BacktestAnalyticsEngine().calculate(req.initial_equity,req.equity_curve,req.trade_pnls,req.periods_per_year))
    except ValueError as e:
        raise HTTPException(status_code=422,detail=str(e))
