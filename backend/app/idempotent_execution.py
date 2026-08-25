from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Callable, Generic, TypeVar


class ExecutionState(str, Enum):
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ExecutionRecord:
    client_order_id: str
    state: ExecutionState
    attempts: int
    result: object | None = None
    error: str | None = None

T = TypeVar("T")


class IdempotentExecution:
    """Prevents duplicate submission for a client order id and bounds retries."""

    def __init__(self, max_attempts: int = 3):
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        self.max_attempts = max_attempts
        self._records: dict[str, ExecutionRecord] = {}
        self._lock = Lock()

    def execute(self, client_order_id: str, submit: Callable[[], T]) -> ExecutionRecord:
        if not client_order_id:
            raise ValueError("client_order_id is required")
        with self._lock:
            existing = self._records.get(client_order_id)
            if existing and existing.state in {ExecutionState.SUBMITTED, ExecutionState.FILLED, ExecutionState.REJECTED}:
                return existing
            attempts = existing.attempts if existing else 0
            if attempts >= self.max_attempts:
                return ExecutionRecord(client_order_id, ExecutionState.UNKNOWN, attempts, error="retry limit reached")
            attempts += 1
            self._records[client_order_id] = ExecutionRecord(client_order_id, ExecutionState.SUBMITTED, attempts)
        try:
            result = submit()
        except Exception as exc:
            with self._lock:
                self._records[client_order_id] = ExecutionRecord(client_order_id, ExecutionState.UNKNOWN, attempts, error=str(exc))
            return self._records[client_order_id]
        with self._lock:
            self._records[client_order_id] = ExecutionRecord(client_order_id, ExecutionState.SUBMITTED, attempts, result=result)
            return self._records[client_order_id]

    def get(self, client_order_id: str) -> ExecutionRecord | None:
        with self._lock:
            return self._records.get(client_order_id)
