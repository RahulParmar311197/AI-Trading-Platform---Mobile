from __future__ import annotations

from datetime import datetime, timezone

from .sql_repository import ExecutionRepository


class SubmissionReconciler:
    """Resolve broker-submission intents without ever re-submitting them."""

    def __init__(self, broker, repository: ExecutionRepository, clock=None):
        self._broker = broker
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def reconcile(self, client_order_id: str) -> dict:
        intent = self._repository.get_intent(client_order_id)
        if intent is None:
            raise KeyError(client_order_id)
        if intent.broker_order_id:
            return {"status": intent.broker_status or "SUBMITTED", "broker_order_id": intent.broker_order_id, "recovered": False}

        orders = self._broker.get_orders()
        matches = [o for o in orders if str(o.get("client_order_id") or "") == client_order_id]
        if len(matches) > 1:
            raise RuntimeError("multiple broker orders match unresolved client_order_id")
        if not matches:
            return {"status": "UNRESOLVED", "broker_order_id": None, "recovered": False}

        match = matches[0]
        broker_order_id = match.get("broker_order_id") or match.get("order_id")
        if not broker_order_id:
            raise RuntimeError("matching broker order has no durable identifier")
        self._repository.resolve_intent(client_order_id, str(broker_order_id), match.get("status"))
        intent.recovered_at = self._clock()
        self._repository.session.flush()
        self._repository.session.commit()
        return {"status": match.get("status") or "SUBMITTED", "broker_order_id": str(broker_order_id), "recovered": True}
