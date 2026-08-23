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
    value = str(status or "").strip().upper().replace("-", "_").replace(" ", "_")
    mapping = {
        "NEW": "SUBMITTED", "OPEN": "SUBMITTED", "ACCEPTED": "SUBMITTED", "PENDING": "SUBMITTED",
        "PENDING_NEW": "SUBMITTED", "TRIGGER_PENDING": "SUBMITTED", "PUT_ORDER_REQ_RECEIVED": "SUBMITTED",
        "VALIDATION_PENDING": "SUBMITTED", "PART_TRADED": "PARTIALLY_FILLED", "PARTIALLY_TRADED": "PARTIALLY_FILLED",
        "PART_FILLED": "PARTIALLY_FILLED", "TRADED": "FILLED", "COMPLETE": "FILLED", "COMPLETED": "FILLED",
        "CANCELED": "CANCELLED", "CANCEL": "CANCELLED", "FAILED": "REJECTED", "ERROR": "REJECTED",
    }
    return mapping.get(value, value)


def _num(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _order_key(order: dict) -> str:
    return str(order.get("client_order_id") or order.get("order_id") or order.get("broker_order_id"))


def _filled(order: dict) -> float:
    return max(0.0, _num(order.get("filled_quantity", order.get("filledQty", order.get("filled_qty", 0)))))


def _average_price(order: dict) -> float | None:
    value = order.get("average_price", order.get("averagePrice", order.get("avg_price")))
    return None if value is None else _num(value, 0.0)


class ReconciliationEngine:
    def __init__(self):
        self.trading_halted = False

    def check(self, internal_orders, broker_orders, internal_positions, broker_positions):
        io = {_order_key(x): x for x in internal_orders}
        bo = {_order_key(x): x for x in broker_orders}
        po = {str(x.get("symbol")).upper(): _num(x.get("quantity")) for x in internal_positions}
        pb = {str(x.get("symbol")).upper(): _num(x.get("quantity")) for x in broker_positions}

        order_drift = []
        for key in set(io) | set(bo):
            if key not in io or key not in bo:
                order_drift.append({"id": key, "internal": io.get(key), "broker": bo.get(key), "reason": "ORDER_MISSING_ON_ONE_SIDE"})
                continue
            internal = io[key]
            broker = bo[key]
            internal_status = normalize_order_status(internal.get("status"))
            broker_status = normalize_order_status(broker.get("status"))
            internal_filled = _filled(internal)
            broker_filled = _filled(broker)
            requested = _num(internal.get("quantity", internal.get("requested_quantity", broker.get("quantity", 0))))
            drift = None
            if internal_status != broker_status:
                drift = "STATUS_MISMATCH"
            elif abs(internal_filled - broker_filled) > 1e-9:
                drift = "FILLED_QUANTITY_MISMATCH"
            elif broker_filled > requested + 1e-9:
                drift = "BROKER_OVERFILL"
            elif internal_status == "FILLED" and abs(broker_filled - requested) > 1e-9:
                drift = "FILLED_WITH_INCOMPLETE_QUANTITY"
            if drift:
                order_drift.append({
                    "id": key,
                    "internal": internal,
                    "broker": broker,
                    "reason": drift,
                    "internal_normalized_status": internal_status,
                    "broker_normalized_status": broker_status,
                    "internal_filled_quantity": internal_filled,
                    "broker_filled_quantity": broker_filled,
                    "requested_quantity": requested,
                })

        position_drift = [
            {"symbol": s, "internal_quantity": po.get(s, 0), "broker_quantity": pb.get(s, 0), "reason": "POSITION_QUANTITY_MISMATCH"}
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
