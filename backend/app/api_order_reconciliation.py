from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Order
from app.order_lifecycle import OrderLifecycle

_NON_TERMINAL_API_STATUSES = {"PENDING", "SUBMISSION_INTENT", "SUBMITTED", "PARTIALLY_FILLED"}


def reconcile_api_order_projection(db: Session, lifecycle: OrderLifecycle) -> list[str]:
    """Reconcile the SQL Order projection from durable execution lifecycle state.

    This is broker-side-effect free: it never submits or cancels an order. Existing
    SQL rows are repaired from lifecycle state. Lifecycle rows missing from SQL are
    materialized only when durable owner metadata is present; otherwise startup
    fails closed rather than inventing account ownership.
    """
    unresolved: list[str] = []
    changed = False
    api_orders = db.query(Order).all()
    api_by_client_id = {str(row.client_order_id).strip(): row for row in api_orders if row.client_order_id}

    for api_order in api_orders:
        client_order_id = str(api_order.client_order_id or "").strip()
        if not client_order_id:
            unresolved.append(f"ORDER:{api_order.id}:MISSING_CLIENT_ORDER_ID")
            continue

        execution_order = lifecycle.orders.get(client_order_id)
        if execution_order is None:
            if str(api_order.status or "").upper() in _NON_TERMINAL_API_STATUSES:
                unresolved.append(f"{client_order_id}:MISSING_EXECUTION_LIFECYCLE")
            continue

        if execution_order.owner_user_id is not None and int(execution_order.owner_user_id) != int(api_order.user_id):
            unresolved.append(f"{client_order_id}:EXECUTION_OWNER_MISMATCH")
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

    for client_order_id, execution_order in lifecycle.orders.items():
        if client_order_id in api_by_client_id:
            continue
        if execution_order.owner_user_id is None:
            unresolved.append(f"{client_order_id}:MISSING_EXECUTION_OWNER")
            continue
        if int(execution_order.owner_user_id) <= 0:
            unresolved.append(f"{client_order_id}:INVALID_EXECUTION_OWNER")
            continue
        lifecycle_status = execution_order.status.value if hasattr(execution_order.status, "value") else str(execution_order.status)
        api_order = Order(
            user_id=int(execution_order.owner_user_id),
            client_order_id=client_order_id,
            symbol=str(execution_order.symbol).upper(),
            side=str(execution_order.side).upper(),
            order_type=str(execution_order.order_type or "MARKET").upper(),
            quantity=float(execution_order.quantity),
            status=lifecycle_status,
            broker_order_id=execution_order.broker_order_id,
            note="RECONCILED_FROM_EXECUTION_LIFECYCLE",
        )
        db.add(api_order)
        api_by_client_id[client_order_id] = api_order
        changed = True

    if changed:
        db.commit()

    return unresolved
