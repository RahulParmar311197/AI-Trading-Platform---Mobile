from __future__ import annotations

from app.broker_adapter import BrokerOrderRequest


class DurableExposureReservationAdapter:
    """Adapt RiskReservationStore to the PreTradeRiskGate reservation contract."""

    def __init__(self, store, max_position_quantity: float):
        self.store = store
        self.max_position_quantity = float(max_position_quantity)
        self._requests: dict[str, BrokerOrderRequest] = {}

    def bind_request(self, request: BrokerOrderRequest) -> None:
        client_id = str(request.client_order_id).strip()
        existing = self._requests.get(client_id)
        if existing is not None:
            if (existing.broker_account_id != request.broker_account_id or
                    existing.broker_route != request.broker_route or
                    existing.side != request.side or
                    float(existing.quantity) != float(request.quantity)):
                raise RuntimeError("risk reservation request binding mismatch")
            return
        if request.broker_account_id is None or not str(request.broker_route or "").strip():
            raise RuntimeError("durable risk reservation requires broker account and route")
        self._requests[client_id] = request

    def _request(self, client_order_id: str) -> BrokerOrderRequest:
        request = self._requests.get(str(client_order_id).strip())
        if request is None:
            raise RuntimeError("risk reservation request binding unavailable")
        return request

    def reserve(self, client_order_id: str, signed_quantity: float, current_position: float, max_position: float) -> bool:
        request = self._request(client_order_id)
        self.store.reserve(
            reservation_id=None,
            client_order_id=client_order_id,
            broker_account_id=str(request.broker_account_id),
            broker_route=str(request.broker_route),
            amount=abs(float(signed_quantity)),
            current_exposure=abs(float(current_position)),
            max_total_exposure=float(max_position),
        )
        return True

    def update(self, client_order_id: str, signed_quantity: float, current_position: float, max_position: float) -> bool:
        self._request(client_order_id)
        remaining = abs(float(signed_quantity))
        self.store.reconcile_client_order(
            client_order_id=client_order_id,
            broker_status="PARTIALLY_FILLED" if remaining > 1e-9 else "FILLED",
            remaining_amount=remaining if remaining > 1e-9 else 0.0,
        )
        return True

    def release(self, client_order_id: str) -> None:
        self._request(client_order_id)
        self.store.reconcile_client_order(client_order_id=client_order_id, broker_status="CANCELLED")

    def get(self, client_order_id: str) -> float | None:
        # Durable store intentionally exposes aggregate safety, not mutable local state.
        return None

    def snapshot(self) -> dict[str, float]:
        return {}

    def rebuild_from_lifecycle(self, lifecycle) -> None:
        # Durable reservations are authoritative and must not be overwritten by
        # a process-local lifecycle rebuild.
        return None
