from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from app.trade_plan import TradePlan,TradeAction
@dataclass(frozen=True)
class PaperOrder:
    order_id:str; symbol:str; action:TradeAction; quantity:int; entry:float; stop_loss:float; take_profit:float; status:str; created_at:datetime
class PaperBroker:
    def __init__(self,initial_cash:float=1_000_000.0):
        if initial_cash<=0: raise ValueError('initial_cash must be positive')
        self.cash=initial_cash; self.orders={}; self._seq=0
    def submit(self,plan:TradePlan)->str:
        self._seq+=1; oid=f'PAPER-{self._seq:08d}'; self.orders[oid]=PaperOrder(oid,plan.symbol,plan.action,plan.quantity,plan.entry,plan.stop_loss,plan.take_profit,'FILLED',datetime.now(timezone.utc)); return oid
    def get_order(self,order_id:str)->PaperOrder|None:return self.orders.get(order_id)
    def mark_to_market(self,order_id:str,price:float)->float:
        order=self.orders[order_id]; direction=1 if order.action==TradeAction.BUY else -1; return (price-order.entry)*order.quantity*direction
