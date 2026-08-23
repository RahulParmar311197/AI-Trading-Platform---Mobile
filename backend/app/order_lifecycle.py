from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

class OrderStatus(str,Enum):
    CREATED='CREATED'; SUBMITTED='SUBMITTED'; PARTIALLY_FILLED='PARTIALLY_FILLED'; FILLED='FILLED'; CANCELLED='CANCELLED'; REJECTED='REJECTED'

class PositionStatus(str,Enum):
    OPEN='OPEN'; CLOSED='CLOSED'

@dataclass
class OrderRecord:
    order_id:str; symbol:str; side:str; quantity:float; status:OrderStatus=OrderStatus.CREATED; filled_quantity:float=0.0; average_fill_price:float|None=None; created_at:datetime=field(default_factory=lambda:datetime.now(timezone.utc)); updated_at:datetime=field(default_factory=lambda:datetime.now(timezone.utc))

@dataclass
class PositionRecord:
    symbol:str; side:str; quantity:float; entry_price:float; status:PositionStatus=PositionStatus.OPEN; exit_price:float|None=None; realized_pnl:float=0.0

class OrderLifecycle:
    def __init__(self): self.orders={}; self.positions={}
    def create(self,order_id,symbol,side,quantity):
        if order_id in self.orders: raise ValueError('duplicate order_id')
        self.orders[order_id]=OrderRecord(order_id,symbol.upper(),side,quantity); return self.orders[order_id]
    def transition(self,order_id,status,filled_quantity=0.0,fill_price=None):
        order=self.orders[order_id]
        if status in (OrderStatus.FILLED,OrderStatus.PARTIALLY_FILLED) and not 0<=filled_quantity<=order.quantity: raise ValueError('invalid filled quantity')
        order.status=status; order.filled_quantity=filled_quantity
        if fill_price is not None: order.average_fill_price=fill_price
        order.updated_at=datetime.now(timezone.utc)
        if status==OrderStatus.FILLED and filled_quantity>0: self._apply_position(order)
        return order
    def _apply_position(self,order):
        existing=self.positions.get(order.symbol)
        if existing is None:
            self.positions[order.symbol]=PositionRecord(order.symbol,order.side,order.filled_quantity,order.average_fill_price or 0.0)
            return
        if existing.side==order.side:
            total=existing.quantity+order.filled_quantity; existing.entry_price=((existing.entry_price*existing.quantity)+(order.average_fill_price or 0)*order.filled_quantity)/total; existing.quantity=total; return
        qty=min(existing.quantity,order.filled_quantity); px=order.average_fill_price or existing.entry_price; existing.realized_pnl+=(px-existing.entry_price)*qty*(1 if existing.side=='BUY' else -1); existing.quantity-=qty
        if existing.quantity<=0: existing.status=PositionStatus.CLOSED; existing.exit_price=px; del self.positions[order.symbol]
