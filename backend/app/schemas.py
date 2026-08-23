from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class Candle(BaseModel):
    symbol: str
    timestamp: datetime
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0

class Signal(BaseModel):
    symbol: str
    direction: Literal["LONG", "SHORT"]
    timeframe: str
    bias: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    bos: bool = False
    mss: bool = False
    liquidity_sweep: bool = False
    fvg: bool = False
    order_block: bool = False
    entry: float
    stop: float
    target: float
    risk_reward: float
    score: int = Field(ge=0, le=100)

class RiskConfig(BaseModel):
    risk_percent: float = Field(default=0.5, gt=0, le=5)
    daily_loss_percent: float = Field(default=2, gt=0, le=20)
    max_positions: int = Field(default=5, ge=1, le=100)
    max_trades_per_day: int = Field(default=10, ge=1, le=1000)

class OrderRequest(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    mode: Literal["PAPER", "LIVE"] = "PAPER"
