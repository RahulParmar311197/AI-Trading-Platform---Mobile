from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Order
from app.order_lifecycle import OrderLifecycle

_NON_TERMINAL_API_STATUSES = {"PENDING", "SUBMISSION_INTENT", "SUBMITTED", "PARTIALLY_FILLED"}


def reconcile_api_order_projection(db: Session, lifecycle: OrderLifecycle) -> list[str]:
    """Repair the SQL Order projection from durable execution lifecycle state.

    This is deliberately broker-side-effect free: it never submits or cancels an
    order. Non-terminal SQL orders missing from the lifecycle are returned as
    unresolved so startup can fail closed instead of guessing.
    """
    unresolved: list[str] = []
    changed = False

    for api_order in db.query(Order).all():
        client_order_id = str(api_order.client_order_id or "").strip()
        if not client_order_id:
            unresolved.append(f"ORDER:{api_order.id}:MISSING_CLIENT_ORDER_ID")
            continue

        execution_order = lifecycle.orders.get(client_order_id)
        if execution_order is None:
            if str(api_order.status or "").upper() in _NON_TERMINAL_API_STATUSES:
                unresolved.append(f"{client_order_id}:MISSING_EXECUTION_LIFECYCLE")
            continue

        lifecycle_status = execution_order.status.value if hasattr(execution_order.status, "value") else str(execution_order.status)
        lifecycle_status = lifecycle_status.upper()
        broker_order_id = execution_order.broker_order_id

        if api_order.status != lifecycle_status:
            api_order.status = lifecycle_status
            changed = True
        if api_order.broker_order_id != broker_order_id:
            api_order.broker_order_id = broker_order_id
            changed = True

    if changed:
        db.commit()

    return unresolved
