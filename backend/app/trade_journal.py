from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class JournalTrade:
    id: str
    symbol: str
    side: str
    entry: float
    exit: float
    quantity: float
    pnl: float
    setup_score: float = 0.0
    strategy: str = "ICT_CONFLUENCE"
    opened_at: str = ""
    closed_at: str = ""
    exit_reason: str = ""


class TradeJournal:
    def __init__(self):
        self.trades: list[JournalTrade] = []

    def record(self, trade: JournalTrade):
        self.trades.append(trade)
        return trade

    def all(self):
        return [asdict(t) for t in self.trades]

    def summary(self):
        pnls = [t.pnl for t in self.trades]
        wins = [x for x in pnls if x > 0]
        losses = [x for x in pnls if x < 0]
        equity = 0.0
        peak = 0.0
        drawdown = 0.0
        curve = []
        for pnl in pnls:
            equity += pnl
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
            curve.append(equity)
        gross_loss = abs(sum(losses))
        return {
            "trade_count": len(pnls),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(pnls) if pnls else 0.0,
            "net_pnl": sum(pnls),
            "average_pnl": sum(pnls) / len(pnls) if pnls else 0.0,
            "profit_factor": sum(wins) / gross_loss if gross_loss else None,
            "max_drawdown": drawdown,
            "equity_curve": curve,
        }


journal = TradeJournal()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
