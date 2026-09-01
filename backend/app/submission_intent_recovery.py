from __future__ import annotations

from app.submission_intent_store import SubmissionIntentStore


def recover_submission_intents(store: SubmissionIntentStore, broker_orders: list[dict]) -> int:
    """Bind and resolve only unambiguous submission intents from one broker snapshot."""
    if not isinstance(broker_orders, list):
        raise ValueError("broker_orders must be a list")

    by_client_id: dict[str, dict] = {}
    for order in broker_orders:
        if not isinstance(order, dict):
            raise ValueError("broker order must be a mapping")
        client_order_id = str(order.get("client_order_id") or order.get("clientOrderId") or "").strip()
        if not client_order_id:
            continue
        if client_order_id in by_client_id:
            raise RuntimeError("duplicate broker client order id during submission intent recovery")
        by_client_id[client_order_id] = order

    recovered = 0
    for intent in store.unresolved():
        order = by_client_id.get(intent.client_order_id)
        if order is None:
            continue

        quantity_value = order.get("quantity", order.get("order_quantity", order.get("qty")))
        if quantity_value is not None:
            try:
                quantity = float(quantity_value)
            except (TypeError, ValueError) as exc:
                raise RuntimeError("matched broker order has invalid quantity") from exc
            if not quantity > 0 or abs(quantity - intent.quantity) > 1e-9:
                raise RuntimeError("submission intent recovery quantity mismatch")

        symbol_value = order.get("symbol", order.get("trading_symbol", order.get("tradingsymbol")))
        if symbol_value is not None and str(symbol_value).strip().upper() != intent.symbol.upper():
            raise RuntimeError("submission intent recovery symbol mismatch")

        side_value = order.get("side", order.get("transaction_type", order.get("transactionType")))
        if side_value is not None and str(side_value).strip().upper() != intent.side.upper():
            raise RuntimeError("submission intent recovery side mismatch")

        broker_order_id = str(
            order.get("broker_order_id") or order.get("order_id") or order.get("orderId") or ""
        ).strip()
        if not broker_order_id:
            raise RuntimeError("matched broker order is missing broker order id")
        broker_status = str(
            order.get("status") or order.get("order_status") or order.get("orderStatus") or ""
        ).strip()
        if not broker_status:
            raise RuntimeError("matched broker order is missing status")

        store.record_broker_order(intent.client_order_id, broker_order_id, broker_status)
        store.resolve(intent.client_order_id)
        recovered += 1

    return recovered
