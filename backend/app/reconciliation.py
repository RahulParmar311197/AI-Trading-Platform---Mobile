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


def normalize_order_status(status: object) -> str:
    """Map broker-specific lifecycle names to the platform canonical states."""
    value = str(status or "").strip().upper().replace("-", "_").replace(" ", "_")
    mapping = {
        "NEW": "SUBMITTED",
        "OPEN": "SUBMITTED",
        "ACCEPTED": "SUBMITTED",
        "PENDING": "SUBMITTED",
        "PENDING_NEW": "SUBMITTED",
        "TRIGGER_PENDING": "SUBMITTED",
        "PUT_ORDER_REQ_RECEIVED": "SUBMITTED",
        "VALIDATION_PENDING": "SUBMITTED",
        "PART_TRADED": "PARTIALLY_FILLED",
        "PARTIALLY_TRADED": "PARTIALLY_FILLED",
        "PART_FILLED": "PARTIALLY_FILLED",
        "TRADED": "FILLED",
        "COMPLETE": "FILLED",
        "COMPLETED": "FILLED",
        "CANCELED": "CANCELLED",
        "CANCEL": "CANCELLED",
        "FAILED": "REJECTED",
        "ERROR": "REJECTED",
    }
    return mapping.get(value, value)


class ReconciliationEngine:
    def __init__(self):
        self.trading_halted = False

    def check(self, internal_orders, broker_orders, internal_positions, broker_positions):
        io = {str(x.get("client_order_id") or x.get("order_id")): x for x in internal_orders}
        bo = {str(x.get("client_order_id") or x.get("broker_order_id")): x for x in broker_orders}
        po = {str(x.get("symbol")).upper(): float(x.get("quantity", 0)) for x in internal_positions}
        pb = {str(x.get("symbol")).upper(): float(x.get("quantity", 0)) for x in broker_positions}

        order_drift = []
        for key in set(io) | set(bo):
            if key not in io or key not in bo:
                order_drift.append({"id": key, "internal": io.get(key), "broker": bo.get(key)})
                continue
            internal_status = normalize_order_status(io[key].get("status"))
            broker_status = normalize_order_status(bo[key].get("status"))
            if internal_status != broker_status:
                order_drift.append({
                    "id": key,
                    "internal": io[key],
                    "broker": bo[key],
                    "internal_normalized_status": internal_status,
                    "broker_normalized_status": broker_status,
                })

        position_drift = [
            {"symbol": s, "internal_quantity": po.get(s, 0), "broker_quantity": pb.get(s, 0)}
            for s in set(po) | set(pb)
            if abs(po.get(s, 0) - pb.get(s, 0)) > 1e-9
        ]
        ok = not order_drift and not position_drift
        if not ok:
            self.trading_halted = True
        return ReconciliationResult(ok, self.trading_halted, order_drift, position_drift, datetime.now(timezone.utc).isoformat())

    def reset_halt(self):
        self.trading_halted = False
        return {"trading_halted": False}
