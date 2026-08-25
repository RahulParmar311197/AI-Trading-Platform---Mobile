from __future__ import annotations

from collections.abc import Callable

from app.transactional_execution_repository import TransactionalExecutionRepository


class ReliableExecutionOutboxPublisher:
    """Publish committed execution messages with durable, expiring delivery leases.

    A crash before acknowledgement leaves the row claimable after the lease expires.
    Delivery remains at-least-once, so consumers must deduplicate by event_id.
    """

    def __init__(self, repository: TransactionalExecutionRepository) -> None:
        self.repository = repository

    def publish_once(self, publish: Callable[[dict], None], *, limit: int = 100, lease_seconds: float = 30.0) -> int:
        published = 0
        for message in self.repository.claim_outbox(limit=limit, lease_seconds=lease_seconds):
            try:
                publish(message)
                self.repository.mark_published(message["id"], message["claim_token"])
                published += 1
            except Exception:
                # Keep the durable claim until it expires so another publisher cannot
                # concurrently deliver the same event. The row becomes retryable after
                # the lease timeout if this process dies or the publish fails.
                raise
        return published

    def retry_pending(self, publish: Callable[[dict], None], *, limit: int = 100, lease_seconds: float = 30.0) -> int:
        return self.publish_once(publish, limit=limit, lease_seconds=lease_seconds)
