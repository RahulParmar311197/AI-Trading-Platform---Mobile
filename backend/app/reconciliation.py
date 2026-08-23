from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True)
class ReconciliationResult:
    ok: bool
    trading_halted: bool
    order_drift: list[dict]
    position_drift: list[dict]
    checked_at: str

class ReconciliationEngine:
    def __init__(self): self.trading_halted=False
    def check(self, internal_orders, broker_orders, internal_positions, broker_positions):
        io={str(x.get("client_order_id") or x.get("order_id")):x for x in internal_orders}
        bo={str(x.get("client_order_id") or x.get("broker_order_id")):x for x in broker_orders}
        po={str(x.get("symbol")).upper():float(x.get("quantity",0)) for x in internal_positions}
        pb={str(x.get("symbol")).upper():float(x.get("quantity",0)) for x in broker_positions}
        order_drift=[{"id":k,"internal":io.get(k),"broker":bo.get(k)} for k in set(io)|set(bo) if k not in io or k not in bo or io[k].get("status")!=bo[k].get("status")]
        position_drift=[{"symbol":s,"internal_quantity":po.get(s,0),"broker_quantity":pb.get(s,0)} for s in set(po)|set(pb) if abs(po.get(s,0)-pb.get(s,0))>1e-9]
        ok=not order_drift and not position_drift
        if not ok:self.trading_halted=True
        return ReconciliationResult(ok,self.trading_halted,order_drift,position_drift,datetime.now(timezone.utc).isoformat())
    def reset_halt(self): self.trading_halted=False; return {"trading_halted":False}
