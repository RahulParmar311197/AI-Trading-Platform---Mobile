from __future__ import annotations

from typing import Any, Protocol

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate, normalize_broker_update
from app.submission_intent_store import SubmissionIntentStore


class BrokerRecoveryReader(Protocol):
    def get_order(self, broker_order_id: str) -> dict[str, Any]: ...


class SubmissionRecoveryError(RuntimeError):
    """Raised when durable submission identity cannot be recovered safely."""


def recover_submission(
    request: BrokerOrderRequest,
    *,
    executor: object,
    intent_store: SubmissionIntentStore,
) -> BrokerOrderUpdate | None:
    """Recover an ambiguous submission using the durable broker binding first.

    Once a broker order id has been durably recorded, it is authoritative. A
    failed lookup for that id must not fall back to a client-id search that
    could discover a different broker order. If no broker id is bound yet,
    exactly one client-id match may establish the durable binding.
    """
    intent = intent_store.get_unresolved(request.client_order_id)
    if intent is None:
        return None

    if intent.broker_order_id is not None:
        getter = getattr(executor, "get_order", None)
        if not callable(getter):
            raise SubmissionRecoveryError(
                "durable broker order binding exists but broker get_order capability is unavailable"
            )
        try:
            raw = getter(intent.broker_order_id)
            verified = normalize_broker_update(raw, expected=request)
        except (TypeError, ValueError, RuntimeError, KeyError) as exc:
            raise SubmissionRecoveryError(
                f"durable broker order recovery failed for broker_order_id={intent.broker_order_id}"
            ) from exc
        if verified.order_id != intent.broker_order_id:
            raise SubmissionRecoveryError("broker returned an order different from the durable binding")
        intent_store.record_broker_order(
            request.client_order_id,
            verified.order_id,
            verified.status,
        )
        return verified

    finder = getattr(executor, "find_order_by_client_id", None)
    if not callable(finder):
        return None
    try:
        raw = finder(request.client_order_id)
        if raw is None:
            return None
        verified = normalize_broker_update(raw, expected=request)
    except (TypeError, ValueError, RuntimeError, KeyError) as exc:
        raise SubmissionRecoveryError(
            f"client-order-id recovery failed for client_order_id={request.client_order_id}"
        ) from exc
    intent_store.record_broker_order(
        request.client_order_id,
        verified.order_id,
        verified.status,
    )
    return verified
