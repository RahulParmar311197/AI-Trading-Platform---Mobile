from __future__ import annotations

from abc import ABC, abstractmethod
from threading import RLock


class ExecutionEventStore(ABC):
    """Durable idempotency boundary for execution events."""

    @abstractmethod
    def contains(self, event_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def record(self, event_id: str) -> None:
        raise NotImplementedError


class InMemoryExecutionEventStore(ExecutionEventStore):
    """Reference implementation; replace with a transactional DB adapter in production."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._event_ids: set[str] = set()

    def contains(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self._event_ids

    def record(self, event_id: str) -> None:
        with self._lock:
            self._event_ids.add(event_id)
