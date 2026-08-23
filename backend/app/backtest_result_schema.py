from __future__ import annotations
from pydantic import BaseModel, Field
class BacktestAnalyticsResponse(BaseModel):
    initial_equity:float; final_equity:float; total_return_pct:float; trades:int; wins:int; losses:int; win_rate_pct:float; profit_factor:float; expectancy:float; max_drawdown_pct:float; sharpe:float; sortino:float; largest_win:float; largest_loss:float; max_consecutive_wins:int; max_consecutive_losses:int
class BacktestRunResponse(BaseModel):
    analytics:BacktestAnalyticsResponse
    equity_curve:list[float]=Field(default_factory=list)
    trade_pnls:list[float]=Field(default_factory=list)
