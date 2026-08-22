from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class KillSwitchState(str,Enum):
    ARMED='ARMED'; DISABLED='DISABLED'

@dataclass(frozen=True)
class LiveGateResult:
    allowed:bool
    reasons:tuple[str,...]

class LiveTradingKillSwitch:
    def __init__(self, enabled:bool=False, confirmation:str|None=None):
        self.state=KillSwitchState.ARMED if enabled else KillSwitchState.DISABLED
        self.confirmation=confirmation

    def arm(self, confirmation:str)->None:
        if confirmation != 'ENABLE_LIVE_TRADING':
            raise ValueError('explicit live trading confirmation required')
        self.state=KillSwitchState.ARMED
        self.confirmation=confirmation

    def disarm(self)->None:
        self.state=KillSwitchState.DISABLED
        self.confirmation=None

    def check(self, configured_live:bool, promotion_live:bool, safety_allowed:bool)->LiveGateResult:
        reasons=[]
        if not configured_live: reasons.append('LIVE_MODE_NOT_CONFIGURED')
        if not promotion_live: reasons.append('STRATEGY_NOT_LIVE_ELIGIBLE')
        if not safety_allowed: reasons.append('SAFETY_GATE_BLOCKED')
        if self.state != KillSwitchState.ARMED: reasons.append('LIVE_KILL_SWITCH_OFF')
        if self.confirmation != 'ENABLE_LIVE_TRADING': reasons.append('LIVE_CONFIRMATION_MISSING')
        return LiveGateResult(not reasons,tuple(reasons))
