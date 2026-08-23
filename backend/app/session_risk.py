from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

@dataclass(frozen=True)
class SessionPolicy:
    timezone_name: str = 'Asia/Kolkata'
    start: time = time(9, 15)
    end: time = time(15, 30)
    block_after_daily_loss_percent: float = 3.0

    def in_session(self, timestamp: datetime) -> bool:
        tz = ZoneInfo(self.timezone_name)
        local = timestamp.replace(tzinfo=timezone.utc).astimezone(tz) if timestamp.tzinfo is None else timestamp.astimezone(tz)
        current = local.timetz().replace(tzinfo=None)
        return self.start <= current <= self.end

    def daily_loss_locked(self, session_start_equity: float, realized_daily_pnl: float) -> bool:
        if session_start_equity <= 0:
            raise ValueError('session_start_equity must be positive')
        loss_pct = max(0.0, -realized_daily_pnl / session_start_equity * 100.0)
        return loss_pct >= self.block_after_daily_loss_percent


def trading_allowed(timestamp: datetime, session_start_equity: float, realized_daily_pnl: float, policy: SessionPolicy | None = None) -> tuple[bool, str]:
    policy = policy or SessionPolicy()
    if not policy.in_session(timestamp):
        return False, 'outside trading session'
    if policy.daily_loss_locked(session_start_equity, realized_daily_pnl):
        return False, 'daily loss lock active'
    return True, 'allowed'
