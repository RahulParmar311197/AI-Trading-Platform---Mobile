from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Order
from app.order_lifecycle import OrderLifecycle

_NON_TERMINAL_API_STATUSES = {"PENDING", "SUBMISSION_INTENT", "SUBMITTED", "PARTIALLY_FILLED"}


def _lifecycle_status(order) -> str:
    value = order.status.value if hasattr(order.status, "value") else str(order.status)
    return value.upper()


def _execution_projection_values(execution_order) -> dict[str, object]:
    return {
        "symbol": str(execution_order.symbol).upper(),
        "side": str(execution_order.side).upper(),
        "order_type": str(execution_order.order_type or "MARKET").upper(),
        "quantity": float(execution_order.quantity),
        "price": execution_order.requested_price,
        "stop": execution_order.stop,
        "security_id": str(execution_order.security_id or ""),
        "status": _lifecycle_status(execution_order),
        "filled_quantity": float(execution_order.filled_quantity),
        "average_fill_price": execution_order.average_fill_price,
        "broker_order_id": execution_order.broker_order_id,
    }


def _apply_projection(api_order: Order, execution_order) -> bool:
    changed = False
    values = _execution_projection_values(execution_order)
    for field, value in values.items():
        current = getattr(api_order, field)
        if current != value:
            setattr(api_order, field, value)
            changed = True
    return changed


def reconcile_api_order_projection(db: Session, lifecycle: OrderLifecycle) -> list[str]:
    """Reconcile SQL orders from durable execution lifecycle state only.

    This function is broker-side-effect free. It repairs the SQL projection from
    the durable execution record and never submits, retries, cancels, or changes
    broker state. Ambiguous ownership is always reported instead of guessed.
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

        if execution_order.owner_user_id is None:
            unresolved.append(f"{client_order_id}:MISSING_EXECUTION_OWNER")
            continue
        if int(execution_order.owner_user_id) <= 0:
            unresolved.append(f"{client_order_id}:INVALID_EXECUTION_OWNER")
            continue
        if int(execution_order.owner_user_id) != int(api_order.user_id):
            unresolved.append(f"{client_order_id}:EXECUTION_OWNER_MISMATCH")
            continue

        changed = _apply_projection(api_order, execution_order) or changed

    for client_order_id, execution_order in lifecycle.orders.items():
        if client_order_id in api_by_client_id:
            continue
        if execution_order.owner_user_id is None:
            unresolved.append(f"{client_order_id}:MISSING_EXECUTION_OWNER")
            continue
        if int(execution_order.owner_user_id) <= 0:
            unresolved.append(f"{client_order_id}:INVALID_EXECUTION_OWNER")
            continue

        values = _execution_projection_values(execution_order)
        api_order = Order(
            user_id=int(execution_order.owner_user_id),
            client_order_id=client_order_id,
            **values,
            note="RECONCILED_FROM_EXECUTION_LIFECYCLE",
        )
        db.add(api_order)
        api_by_client_id[client_order_id] = api_order
        changed = True

    if changed:
        db.commit()

    return unresolved
