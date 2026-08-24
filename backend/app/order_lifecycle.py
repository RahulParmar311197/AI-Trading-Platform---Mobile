from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from app.trading_audit import TradingAuditLog

class OrderStatus(str, Enum):
    CREATED="CREATED"; SUBMISSION_INTENT="SUBMISSION_INTENT"; SUBMITTED="SUBMITTED"; PARTIALLY_FILLED="PARTIALLY_FILLED"; FILLED="FILLED"; CANCELLED="CANCELLED"; REJECTED="REJECTED"
class PositionStatus(str, Enum): OPEN="OPEN"; CLOSED="CLOSED"

@dataclass
class OrderRecord:
    order_id:str; symbol:str; side:str; quantity:float
    status:OrderStatus=OrderStatus.CREATED; filled_quantity:float=0.0; average_fill_price:float|None=None
    applied_fill_quantity:float=0.0; applied_fill_value:float=0.0; broker_order_id:str|None=None
    order_type:str="MARKET"; requested_price:float|None=None; stop:float|None=None; target:float|None=None
    security_id:str=""; exchange_segment:str="NSE_EQ"; product_type:str="CNC"; validity:str="DAY"; trigger_price:float|None=None
    risk_amount:float|None=None; risk_source:str|None=None; risk_confidence:float|None=None; risk_reason:str|None=None
    created_at:datetime=field(default_factory=lambda:datetime.now(timezone.utc)); updated_at:datetime=field(default_factory=lambda:datetime.now(timezone.utc))

@dataclass
class PositionRecord:
    symbol:str; side:str; quantity:float; entry_price:float; status:PositionStatus=PositionStatus.OPEN; exit_price:float|None=None; realized_pnl:float=0.0

class OrderLifecycle:
    def __init__(self, audit_log:TradingAuditLog|None=None):
        self.orders={}; self.positions={}; self.realized_pnl_by_symbol={}; self.realized_pnl_by_day={}; self._applied_fill_ids=set(); self.audit_log=audit_log or TradingAuditLog()
    def create(self,order_id,symbol,side,quantity,**metadata):
        if order_id in self.orders: raise ValueError("duplicate order_id")
        allowed={k:v for k,v in metadata.items() if k in OrderRecord.__dataclass_fields__}
        order=OrderRecord(order_id,symbol.upper(),side.upper(),quantity,**allowed); self.orders[order_id]=order
        self.audit_log.record("ORDER_CREATED", metadata={"order_id":order_id,"symbol":order.symbol,"side":order.side,"quantity":quantity})
        return order

    def apply_fill(self, order_id, quantity, price, fill_id=None):
        """Apply one execution fill event; repeated fill_id values are ignored."""
        if fill_id is not None and fill_id in self._applied_fill_ids: return self.orders[order_id]
        order=self.orders[order_id]; quantity=float(quantity); price=float(price)
        if quantity<=0: raise ValueError("fill quantity must be positive")
        if price<=0: raise ValueError("fill price must be positive")
        if order.filled_quantity + quantity > order.quantity: raise ValueError("invalid filled quantity")
        new_filled=order.filled_quantity + quantity; new_value=order.applied_fill_value + quantity*price
        order.filled_quantity=new_filled; order.average_fill_price=new_value/new_filled; order.applied_fill_quantity=new_filled; order.applied_fill_value=new_value
        order.status=OrderStatus.FILLED if new_filled==order.quantity else OrderStatus.PARTIALLY_FILLED; order.updated_at=datetime.now(timezone.utc)
        self._apply_position_delta(order,quantity,price)
        if fill_id is not None: self._applied_fill_ids.add(fill_id)
        self.audit_log.record("ORDER_FILL", metadata={"order_id":order_id,"fill_id":fill_id,"quantity":quantity,"price":price,"cumulative_filled":new_filled,"status":order.status.value})
        return order

    def transition(self,order_id,status,filled_quantity=0.0,fill_price=None):
        """Reconcile a broker snapshot where fill_price is the cumulative average price."""
        order=self.orders[order_id]; previous=order.status
        if status in (OrderStatus.FILLED,OrderStatus.PARTIALLY_FILLED) and not 0<=filled_quantity<=order.quantity: raise ValueError("invalid filled quantity")
        if filled_quantity<order.applied_fill_quantity: raise ValueError("filled quantity cannot move backwards")
        order.status=status; order.filled_quantity=filled_quantity
        if fill_price is not None:
            fill_price=float(fill_price)
            if fill_price<=0: raise ValueError("fill price must be positive")
            order.average_fill_price=fill_price
        order.updated_at=datetime.now(timezone.utc); delta_quantity=filled_quantity-order.applied_fill_quantity
        if delta_quantity>0:
            if order.average_fill_price is None: raise ValueError("fill price is required when applying a fill")
            cumulative_value=filled_quantity*order.average_fill_price; delta_value=cumulative_value-order.applied_fill_value
            if delta_value<=0: raise ValueError("cumulative fill value cannot move backwards")
            self._apply_position_delta(order,delta_quantity,delta_value/delta_quantity); order.applied_fill_quantity=filled_quantity; order.applied_fill_value=cumulative_value
            self.audit_log.record("ORDER_FILL_RECONCILED", metadata={"order_id":order_id,"quantity":delta_quantity,"price":delta_value/delta_quantity,"cumulative_filled":filled_quantity})
        if previous != status:
            self.audit_log.record("ORDER_STATE_CHANGE", from_state=previous.value, to_state=status.value, metadata={"order_id":order_id,"filled_quantity":filled_quantity})
        return order

    def _record_realized_pnl(self,symbol,pnl,when=None):
        self.realized_pnl_by_symbol[symbol]=self.realized_pnl_by_symbol.get(symbol,0.0)+pnl; day=(when or datetime.now(timezone.utc)).astimezone(timezone.utc).date().isoformat(); self.realized_pnl_by_day[day]=self.realized_pnl_by_day.get(day,0.0)+pnl
    def _apply_position_delta(self,order,quantity,price):
        existing=self.positions.get(order.symbol)
        if existing is None: self.positions[order.symbol]=PositionRecord(order.symbol,order.side,quantity,price); return
        if existing.side==order.side:
            total=existing.quantity+quantity; existing.entry_price=((existing.entry_price*existing.quantity)+(price*quantity))/total; existing.quantity=total; return
        closing_qty=min(existing.quantity,quantity); pnl=(price-existing.entry_price)*closing_qty*(1 if existing.side=="BUY" else -1); existing.realized_pnl+=pnl; self._record_realized_pnl(order.symbol,pnl); remaining=quantity-closing_qty; existing.quantity-=closing_qty
        if existing.quantity>0: existing.exit_price=price; return
        del self.positions[order.symbol]
        if remaining>0:self.positions[order.symbol]=PositionRecord(order.symbol,order.side,remaining,price)
