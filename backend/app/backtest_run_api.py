from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.backtest_service import BacktestService

router = APIRouter(prefix='/api/v1/backtests', tags=['backtests'])

class BacktestRunRequest(BaseModel):
    symbol: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    start: datetime
    end: datetime
    initial_equity: float = Field(gt=0)
    risk_pct: float = Field(default=1.0, gt=0, le=100)
    data_root: str = Field(default='data/historical', min_length=1)

@router.post('/run')
def run_backtest(req: BacktestRunRequest):
    if req.start >= req.end:
        raise HTTPException(status_code=422, detail='start must be before end')
    if req.start.tzinfo is None or req.end.tzinfo is None:
        raise HTTPException(status_code=422, detail='start and end must include timezone')
    try:
        return BacktestService(req.data_root).run(req.symbol, req.timeframe, req.start, req.end, req.initial_equity, req.risk_pct)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'backtest execution failed: {exc}')
