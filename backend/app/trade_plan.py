from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

class TradeAction(str,Enum): BUY='BUY'; SELL='SELL'
@dataclass(frozen=True)
class TradePlan:
    symbol:str; action:TradeAction; entry:float; stop_loss:float; take_profit:float; quantity:int; risk_amount:float; reward_amount:float; risk_reward:float; expires_at:datetime
class TradePlanValidator:
    def __init__(self,min_rr:float=1.5,max_expiry_minutes:int=1440): self.min_rr=min_rr; self.max_expiry_minutes=max_expiry_minutes
    def build(self,symbol,action,entry,stop_loss,take_profit,quantity,risk_amount,expiry_minutes=60):
        if not symbol or min(entry,stop_loss,take_profit)<=0 or quantity<1 or risk_amount<=0: raise ValueError('invalid trade plan inputs')
        if expiry_minutes<1 or expiry_minutes>self.max_expiry_minutes: raise ValueError('invalid expiry')
        risk=abs(entry-stop_loss)*quantity; reward=abs(take_profit-entry)*quantity; rr=reward/risk if risk else 0
        if action==TradeAction.BUY and not stop_loss<entry<take_profit: raise ValueError('invalid BUY levels')
        if action==TradeAction.SELL and not take_profit<entry<stop_loss: raise ValueError('invalid SELL levels')
        if rr<self.min_rr: raise ValueError('risk reward below minimum')
        if risk>risk_amount+1e-9: raise ValueError('planned loss exceeds approved risk')
        return TradePlan(symbol,action,entry,stop_loss,take_profit,quantity,risk_amount,reward,rr,datetime.now(timezone.utc)+timedelta(minutes=expiry_minutes))
