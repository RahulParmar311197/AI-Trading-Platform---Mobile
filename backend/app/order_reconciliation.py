from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from app.order_lifecycle import OrderLifecycle, OrderStatus

class ReconciliationAction(str,Enum):
    NOOP='NOOP'; CREATE='CREATE'; UPDATE='UPDATE'; ALERT='ALERT'

@dataclass(frozen=True)
class BrokerOrder:
    order_id:str; symbol:str; side:str; quantity:float; status:OrderStatus; filled_quantity:float=0.0; average_fill_price:float|None=None

@dataclass(frozen=True)
class ReconciliationEvent:
    order_id:str; action:ReconciliationAction; reason:str

class OrderReconciler:
    def __init__(self,lifecycle:OrderLifecycle): self.lifecycle=lifecycle
    def reconcile(self,broker_orders:list[BrokerOrder])->list[ReconciliationEvent]:
        events=[]; seen=set()
        for remote in broker_orders:
            if remote.order_id in seen:
                events.append(ReconciliationEvent(remote.order_id,ReconciliationAction.ALERT,'DUPLICATE_BROKER_UPDATE')); continue
            seen.add(remote.order_id); local=self.lifecycle.orders.get(remote.order_id)
            if local is None:
                self.lifecycle.create(remote.order_id,remote.symbol,remote.side,remote.quantity)
                self.lifecycle.transition(remote.order_id,remote.status,remote.filled_quantity,remote.average_fill_price)
                events.append(ReconciliationEvent(remote.order_id,ReconciliationAction.CREATE,'MISSING_LOCAL_ORDER')); continue
            if (local.status,local.filled_quantity,local.average_fill_price)!=(remote.status,remote.filled_quantity,remote.average_fill_price):
                self.lifecycle.transition(remote.order_id,remote.status,remote.filled_quantity,remote.average_fill_price)
                events.append(ReconciliationEvent(remote.order_id,ReconciliationAction.UPDATE,'LOCAL_STATE_RECONCILED'))
            else: events.append(ReconciliationEvent(remote.order_id,ReconciliationAction.NOOP,'ALREADY_IN_SYNC'))
        return events
