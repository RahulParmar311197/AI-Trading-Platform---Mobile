from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from app.trade_plan import TradePlan,TradeAction

@dataclass(frozen=True)
class ExecutionResult:
    accepted:bool
    order_id:str|None
    reason:str

class BrokerAdapter:
    def submit(self,plan:TradePlan)->str:
        raise NotImplementedError

class ExecutionOrchestrator:
    def __init__(self,broker:BrokerAdapter,live_enabled:bool=False): self.broker=broker; self.live_enabled=live_enabled
    def submit(self,plan:TradePlan,kill_switch_armed:bool=False)->ExecutionResult:
        if not self.live_enabled:return ExecutionResult(False,None,'LIVE_EXECUTION_DISABLED')
        if not kill_switch_armed:return ExecutionResult(False,None,'KILL_SWITCH_BLOCKED')
        if plan.expires_at<=datetime.now(timezone.utc):return ExecutionResult(False,None,'TRADE_PLAN_EXPIRED')
        if plan.quantity<1:return ExecutionResult(False,None,'INVALID_QUANTITY')
        if plan.action not in (TradeAction.BUY,TradeAction.SELL):return ExecutionResult(False,None,'INVALID_ACTION')
        order_id=self.broker.submit(plan); return ExecutionResult(True,order_id,'ORDER_SUBMITTED')
