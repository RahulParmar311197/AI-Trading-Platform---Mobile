from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ReconciliationSnapshot:
    fingerprint: str
    generation: int


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canonical(value[k]) for k in sorted(value, key=lambda k: str(k))}
    if isinstance(value, (list, tuple)):
        items = [_canonical(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("snapshot contains non-finite number")
        return value
    return value


def snapshot_fingerprint(*, positions: Sequence[Mapping[str, Any]], orders: Sequence[Mapping[str, Any]] = ()) -> str:
    payload = _canonical({"positions": positions, "orders": orders})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def next_snapshot(previous: ReconciliationSnapshot | None, *, positions: Sequence[Mapping[str, Any]], orders: Sequence[Mapping[str, Any]] = ()) -> ReconciliationSnapshot:
    fingerprint = snapshot_fingerprint(positions=positions, orders=orders)
    if previous is None:
        return ReconciliationSnapshot(fingerprint=fingerprint, generation=1)
    generation = previous.generation if previous.fingerprint == fingerprint else previous.generation + 1
    return ReconciliationSnapshot(fingerprint=fingerprint, generation=generation)
