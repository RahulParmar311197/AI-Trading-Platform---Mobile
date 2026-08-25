from __future__ import annotations

from collections.abc import Callable

from app.transactional_execution_repository import TransactionalExecutionRepository


class ReliableExecutionOutboxPublisher:
    """Publish committed execution messages and acknowledge only after success.

    A crash before mark_published leaves the row pending, so delivery is at-least-once.
    Consumers must deduplicate by event_id.
    """

    def __init__(self, repository: TransactionalExecutionRepository) -> None:
        self.repository = repository

    def publish_once(self, publish: Callable[[dict], None], *, limit: int = 100) -> int:
        published = 0
        for message in self.repository.pending_outbox(limit):
            publish(message)
            self.repository.mark_published(message["id"])
            published += 1
        return published

    def retry_pending(self, publish: Callable[[dict], None], *, limit: int = 100) -> int:
        return self.publish_once(publish, limit=limit)
