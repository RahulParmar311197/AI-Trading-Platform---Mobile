from __future__ import annotations

from collections.abc import Callable

from app.durable_execution_consumer import DurableExecutionConsumer
from app.transactional_execution_repository import TransactionalExecutionRepository


class ExecutionOutboxRecoveryWorker:
    """Drain committed execution outbox messages through a durable consumer.

    Producer acknowledgement happens only after the downstream consumer commits.
    A crash before acknowledgement leaves the outbox row pending; consumer event_id
    deduplication makes retry safe.
    """

    def __init__(self, repository: TransactionalExecutionRepository, consumer: DurableExecutionConsumer) -> None:
        self.repository = repository
        self.consumer = consumer

    def drain_once(self, handler: Callable[[dict], None], *, limit: int = 100) -> int:
        acknowledged = 0
        for message in self.repository.pending_outbox(limit):
            self.consumer.consume(message, handler)
            self.repository.mark_published(message["id"])
            acknowledged += 1
        return acknowledged
