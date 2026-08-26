from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from app.reconciliation_result import ReconciliationResult
from app.reconciliation_validation import validate_reconciliation_inputs

_CHECK_TOKEN = object()


@dataclass(frozen=True, init=False)
class ReconciliationCheckResult:
    """Authenticated result of one reconciliation engine execution."""
    ok: bool
    trading_halted: bool
    order_drift: list[dict]
    position_drift: list[dict]
    checked_at: str
    _verification_token: object

    def __init__(self, *, ok: bool, trading_halted: bool, order_drift: list[dict], position_drift: list[dict], checked_at: str, _verification_token: object) -> None:
        if _verification_token is not _CHECK_TOKEN:
            raise TypeError("use ReconciliationEngine.check")
        if ok and (order_drift or position_drift):
            raise ValueError("successful reconciliation cannot contain drift")
        if not checked_at.strip():
            raise ValueError("checked_at is required")
        object.__setattr__(self, "ok", bool(ok))
        object.__setattr__(self, "trading_halted", bool(trading_halted))
        object.__setattr__(self, "order_drift", list(order_drift))
        object.__setattr__(self, "position_drift", list(position_drift))
        object.__setattr__(self, "checked_at", checked_at)
        object.__setattr__(self, "_verification_token", _CHECK_TOKEN)

    @property
    def verified(self) -> bool:
        return self._verification_token is _CHECK_TOKEN


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


def _side_sign(value: object) -> int:
    side = str(value or "").strip().upper()
    if side in {"BUY", "B", "LONG", "1", "+1"}:
        return 1
    if side in {"SELL", "S", "SHORT", "-1"}:
        return -1
    return 0


def _signed_position(position: dict) -> float:
    if "signed_quantity" in position:
        return _num(position.get("signed_quantity"))
    quantity = _num(position.get("quantity", position.get("net_quantity", position.get("netQty", 0))))
    if "side" in position:
        sign = _side_sign(position.get("side"))
        if sign == 0 and abs(quantity) > 1e-9:
            raise ValueError(f"unknown position side: {position.get('side')}")
        return abs(quantity) * sign
    return quantity


class ReconciliationEngine:
    def __init__(self):
        self.trading_halted = False

    def check(self, internal_orders, broker_orders, internal_positions, broker_positions) -> ReconciliationCheckResult:
        io_list, bo_list, ip_list, bp_list = validate_reconciliation_inputs(
            internal_orders, broker_orders, internal_positions, broker_positions
        )
        io = {_order_key(x): x for x in io_list}
        bo = {_order_key(x): x for x in bo_list}
        po = {str(x.get("symbol")).upper(): _signed_position(x) for x in ip_list}
        pb = {str(x.get("symbol")).upper(): _signed_position(x) for x in bp_list}

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
                order_drift.append({"id": key, "internal": internal, "broker": broker, "reason": drift, "internal_normalized_status": internal_status, "broker_normalized_status": broker_status, "internal_filled_quantity": internal_filled, "broker_filled_quantity": broker_filled, "requested_quantity": requested})

        position_drift = [
            {"symbol": s, "internal_signed_quantity": po.get(s, 0), "broker_signed_quantity": pb.get(s, 0), "reason": "POSITION_SIGNED_QUANTITY_MISMATCH"}
            for s in set(po) | set(pb)
            if abs(po.get(s, 0) - pb.get(s, 0)) > 1e-9
        ]
        ok = not order_drift and not position_drift
        if not ok:
            self.trading_halted = True
        return ReconciliationCheckResult(ok=ok, trading_halted=self.trading_halted, order_drift=order_drift, position_drift=position_drift, checked_at=datetime.now(timezone.utc).isoformat(), _verification_token=_CHECK_TOKEN)

    def build_verified_result(self, check: ReconciliationCheckResult, *, account_id: str, generation: int, reconciled_at: datetime, open_orders_reconciled: bool, positions_reconciled: bool, submission_intents_resolved: int, broker_ready: bool, broker_snapshot_fingerprint: str) -> ReconciliationResult:
        if not isinstance(check, ReconciliationCheckResult) or not check.verified:
            raise ValueError("authenticated reconciliation check is required")
        if not check.ok or check.trading_halted or check.order_drift or check.position_drift:
            raise ValueError("cannot build verified result from failed reconciliation")
        return ReconciliationResult.from_verified_check(
            account_id=account_id,
            generation=generation,
            reconciled_at=reconciled_at,
            open_orders_reconciled=open_orders_reconciled,
            positions_reconciled=positions_reconciled,
            submission_intents_resolved=submission_intents_resolved,
            broker_ready=broker_ready,
            broker_snapshot_fingerprint=broker_snapshot_fingerprint,
            _check_token=_CHECK_TOKEN,
        )

    def reset_halt(self):
        self.trading_halted = False
        return {"trading_halted": False}
