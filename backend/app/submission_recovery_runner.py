from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from app.order_submission_recovery_orchestrator import OrderSubmissionRecoveryOrchestrator, RecoveryResult
from app.submission_recovery_authorization import RecoveryApproval


@dataclass(frozen=True)
class RecoveryStats:
    scanned: int
    submitted: int
    quarantined: int
    duration_ms: float


@dataclass(frozen=True)
class RecoveryRun:
    results: list[RecoveryResult]
    stats: RecoveryStats


class SubmissionRecoveryRunner:
    """Bounded, framework-independent recovery entrypoint with explicit operator scope."""

    def __init__(self, orchestrator: OrderSubmissionRecoveryOrchestrator) -> None:
        self.orchestrator = orchestrator

    def run_once(self, *, approval: RecoveryApproval, limit: int = 100) -> RecoveryRun:
        if limit <= 0 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        started = monotonic()
        results = self.orchestrator.recover_pending(limit=limit, approval=approval)
        submitted = sum(r.status == "SUBMITTED" for r in results)
        quarantined = sum(r.status == "QUARANTINED" for r in results)
        return RecoveryRun(results, RecoveryStats(len(results), submitted, quarantined, (monotonic() - started) * 1000))
