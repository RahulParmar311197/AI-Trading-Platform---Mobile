from __future__ import annotations

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.live_execution_gateway import LiveExecutionGateway
from app.submission_recovery import recover_submission
from app.submission_intent_store import SubmissionIntentStore


class AuthoritativeLiveExecutionGateway(LiveExecutionGateway):
    """Live gateway whose ambiguous-submission recovery is durable-binding aware."""

    def __init__(self, *args, submission_intent_store: SubmissionIntentStore, **kwargs) -> None:
        super().__init__(*args, submission_intent_store=submission_intent_store, **kwargs)

    def _recover_ambiguous_submission(self, request: BrokerOrderRequest) -> BrokerOrderUpdate | None:
        return recover_submission(
            request,
            executor=self.executor,
            intent_store=self.submission_intent_store,
        )
