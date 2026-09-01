from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.api.markets import demo_candles
from app.backtest import BacktestConfig, CandleBacktester
from app.market_data import Candle
from app.performance_metrics import calculate_performance_metrics

router = APIRouter(tags=["backtest"])


def _to_candle(item: dict, symbol: str) -> Candle:
    timestamp = item.get("timestamp")
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="invalid candle timestamp") from exc
    elif isinstance(timestamp, (int, float)):
        timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if not isinstance(timestamp, datetime):
        raise HTTPException(status_code=422, detail="invalid candle timestamp")
    return Candle(
        timestamp=timestamp,
        symbol=symbol,
        timeframe=str(item.get("timeframe", "5m")),
        open=float(item["open"]),
        high=float(item["high"]),
        low=float(item["low"]),
        close=float(item["close"]),
        volume=float(item.get("volume", 0.0)),
    )


@router.post("/backtest")
def backtest(symbol: str = "NIFTY", bars: int = 1000, capital: float = 100000, risk_percent: float = 0.5):
    if capital <= 0:
        raise HTTPException(status_code=422, detail="capital must be positive")
    if not 0 < risk_percent <= 100:
        raise HTTPException(status_code=422, detail="risk_percent must be greater than 0 and at most 100")

    bounded_bars = min(max(bars, 50), 2000)
    raw = demo_candles(symbol, bounded_bars)
    candles = [_to_candle(item, symbol) for item in raw]
    result = CandleBacktester(BacktestConfig(initial_equity=capital)).run(candles)
    journal = list(result.trades)
    trade_pnls = [float(item.get("pnl", 0.0)) for item in journal if isinstance(item, dict)]
    metrics = calculate_performance_metrics(
        result.equity_curve,
        trade_pnls,
        initial_equity=result.initial_equity,
    )
    return {
        "initial_equity": result.initial_equity,
        "final_equity": result.final_equity,
        "net_pnl": result.final_equity - result.initial_equity,
        "gross_pnl": metrics.gross_profit - metrics.gross_loss,
        "fees": 0.0,
        "equity_curve": list(result.equity_curve),
        "metrics": metrics,
        "trades": journal,
    }
