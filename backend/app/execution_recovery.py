from __future__ import annotations
from dataclasses import dataclass
from app.order_lifecycle import OrderLifecycle, PositionRecord
from app.order_reconciliation import OrderReconciler, BrokerOrder, ReconciliationEvent

@dataclass(frozen=True)
class BrokerPosition:
    symbol:str; side:str; quantity:float; entry_price:float

@dataclass(frozen=True)
class RecoveryReport:
    order_events:list[ReconciliationEvent]
    position_mismatches:list[str]
    safe_to_resume:bool

class ExecutionRecovery:
    def __init__(self,lifecycle:OrderLifecycle): self.lifecycle=lifecycle
    def recover(self, broker_orders:list[BrokerOrder], broker_positions:list[BrokerPosition])->RecoveryReport:
        events=OrderReconciler(self.lifecycle).reconcile(broker_orders)
        mismatches=[]
        local={k:v for k,v in self.lifecycle.positions.items()}
        remote={p.symbol:p for p in broker_positions}
        for symbol in sorted(set(local)|set(remote)):
            l=local.get(symbol); r=remote.get(symbol)
            if l is None or r is None: mismatches.append(f'{symbol}:POSITION_MISSING_ON_ONE_SIDE'); continue
            if l.side!=r.side or abs(l.quantity-r.quantity)>1e-9 or abs(l.entry_price-r.entry_price)>1e-6:
                mismatches.append(f'{symbol}:POSITION_STATE_MISMATCH')
        return RecoveryReport(events,mismatches,not mismatches and not any(e.action.value=='ALERT' for e in events))
