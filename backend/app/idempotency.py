from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol


class IdempotencyStore(Protocol):
    def claim(self, key: str, value: str, ttl_seconds: int) -> bool: ...


class InMemoryIdempotencyStore:
    """Deterministic store for tests and single-process paper execution only."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def claim(self, key: str, value: str, ttl_seconds: int) -> bool:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if key in self._values:
            return False
        self._values[key] = value
        return True


class RedisIdempotencyStore:
    """Atomic distributed claim backed by Redis SET NX EX."""

    def __init__(self, redis_client: Any) -> None:
        self.redis = redis_client

    def claim(self, key: str, value: str, ttl_seconds: int) -> bool:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        return bool(self.redis.set(key, value, nx=True, ex=ttl_seconds))


def order_idempotency_key(*, account_id: str, broker: str, request_id: str) -> str:
    """Build a stable namespace key for one execution request."""
    account_id = account_id.strip()
    broker = broker.strip().lower()
    request_id = request_id.strip()
    if not account_id or not broker or not request_id:
        raise ValueError("account_id, broker and request_id are required")
    return f"trade:idempotency:{account_id}:{broker}:{request_id}"


def order_fingerprint(order: dict[str, Any]) -> str:
    """Canonical fingerprint used to detect accidental request mutation/reuse."""
    payload = json.dumps(order, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IdempotencyClaim:
    key: str
    fingerprint: str
    claimed: bool


def claim_order(
    store: IdempotencyStore,
    *,
    account_id: str,
    broker: str,
    request_id: str,
    order: dict[str, Any],
    ttl_seconds: int = 86400,
) -> IdempotencyClaim:
    key = order_idempotency_key(
        account_id=account_id, broker=broker, request_id=request_id
    )
    fingerprint = order_fingerprint(order)
    return IdempotencyClaim(
        key=key,
        fingerprint=fingerprint,
        claimed=store.claim(key, fingerprint, ttl_seconds),
    )
