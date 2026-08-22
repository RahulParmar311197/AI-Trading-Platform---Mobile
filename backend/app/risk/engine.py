from dataclasses import dataclass
from app.schemas import RiskConfig, OrderRequest

@dataclass
class RiskDecision:
    approved: bool
    reasons: list[str]

class RiskEngine:
    def validate(self, order: OrderRequest, cfg: RiskConfig, equity: float, daily_pnl: float, open_positions: int, trades_today: int, market_fresh: bool = True, broker_healthy: bool = True) -> RiskDecision:
        reasons=[]
        if not market_fresh: reasons.append("MARKET_DATA_STALE")
        if not broker_healthy and order.mode == "LIVE": reasons.append("BROKER_UNHEALTHY")
        if open_positions >= cfg.max_positions: reasons.append("MAX_POSITIONS")
        if trades_today >= cfg.max_trades_per_day: reasons.append("MAX_TRADES_PER_DAY")
        if equity <= 0: reasons.append("INVALID_EQUITY")
        if daily_pnl <= -(equity * cfg.daily_loss_percent / 100): reasons.append("DAILY_LOSS_LIMIT")
        if order.quantity <= 0: reasons.append("INVALID_QUANTITY")
        return RiskDecision(not reasons, reasons)
