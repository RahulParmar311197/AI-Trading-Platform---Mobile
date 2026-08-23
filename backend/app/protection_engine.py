from __future__ import annotations
from dataclasses import dataclass

@dataclass
class ProtectionConfig:
    breakeven_trigger_r: float = 1.0
    breakeven_buffer_pct: float = 0.0002
    trailing_trigger_r: float = 1.5
    trailing_distance_r: float = 1.0
    partial_trigger_r: float = 2.0
    partial_exit_pct: float = 0.5

@dataclass(frozen=True)
class ProtectionAction:
    action: str
    stop: float | None = None
    exit_quantity: float = 0.0
    reason: str = ""

def evaluate(*, side: str, entry: float, current: float, stop: float, quantity: float, config: ProtectionConfig) -> ProtectionAction:
    if min(entry,current,stop,quantity) <= 0: raise ValueError("prices and quantity must be positive")
    direction = 1 if side.upper() == "BUY" else -1
    initial_risk = abs(entry-stop)
    if initial_risk <= 0: raise ValueError("invalid initial stop")
    r = ((current-entry)*direction)/initial_risk
    if r >= config.partial_trigger_r: return ProtectionAction("PARTIAL_EXIT", stop, quantity*config.partial_exit_pct, f"{r:.2f}R profit target reached")
    if r >= config.trailing_trigger_r:
        candidate=current-direction*(initial_risk*config.trailing_distance_r)
        if (direction==1 and candidate>stop) or (direction==-1 and candidate<stop): return ProtectionAction("TRAIL",candidate,0.0,f"trailing stop at {r:.2f}R")
    if r >= config.breakeven_trigger_r:
        candidate=entry*(1+direction*config.breakeven_buffer_pct)
        if (direction==1 and candidate>stop) or (direction==-1 and candidate<stop): return ProtectionAction("BREAKEVEN",candidate,0.0,f"breakeven at {r:.2f}R")
    return ProtectionAction("HOLD",stop,0.0,f"holding at {r:.2f}R")
