from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import secrets
from typing import Any, Callable, Protocol

from app.broker_order_lifecycle import OrderLifecycle, OrderLifecycleEvent, OrderStatus
from app.order_intent import OrderIntent
from app.pre_trade_reconciliation_gate import PreTradeReconciliationGate, PreTradeReconciliationPolicy
from app.trading_incidents import IncidentReporter


class ExecutionMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class ExecutionSafetyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutionPolicy:
    mode: ExecutionMode = ExecutionMode.PAPER
    live_trading_enabled: bool = False
    kill_switch: bool = False
    reconciliation_enabled: bool = True
    authorization_ttl_seconds: int = 10


class BrokerExecutor(Protocol):
    def execute(self, order: OrderIntent): ...


class BrokerPositionReader(Protocol):
    def get_positions(self) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class ExecutionAuthorization:
    """Single-use, gateway-issued authorization bound to one normalized order."""

    _nonce: str
    _order_fingerprint: str
    _expires_at: datetime


@dataclass(frozen=True)
class TrackedExecution:
    result: object
    lifecycle: OrderLifecycle


class LiveExecutionGateway:
    """Single safety boundary between approved trade intents and broker execution."""

    def __init__(self, executor: BrokerExecutor, policy: ExecutionPolicy | None = None, *, position_reader: BrokerPositionReader | None = None, local_positions_reader: Callable[[], list[dict[str, Any]]] | None = None, incident_reporter: IncidentReporter | None = None) -> None:
        self.executor = executor
        self.policy = policy or ExecutionPolicy()
        self.position_reader = position_reader
        self.local_positions_reader = local_positions_reader
        self.incident_reporter = incident_reporter or IncidentReporter()
        self._authorizations: dict[str, ExecutionAuthorization] = {}

    def authorize(self, order: OrderIntent) -> ExecutionAuthorization:
        """Validate a live order against current broker/local positions and issue one-use authorization."""
        if self.policy.kill_switch:
            self.incident_reporter.report_kill_switch("execution blocked: kill switch is active")
            raise ExecutionSafetyError("execution blocked: kill switch is active")
        if self.policy.mode is not ExecutionMode.LIVE:
            raise ExecutionSafetyError("execution authorization is only required for live mode")
        if not self.policy.live_trading_enabled:
            raise ExecutionSafetyError("live execution is disabled")
        safe_order = self._validate_order(order)
        self._check_reconciliation()
        ttl = int(self.policy.authorization_ttl_seconds)
        if ttl <= 0:
            raise ExecutionSafetyError("execution authorization TTL must be positive")
        token = ExecutionAuthorization(
            _nonce=secrets.token_urlsafe(32),
            _order_fingerprint=_fingerprint(safe_order),
            _expires_at=_now() + timedelta(seconds=ttl),
        )
        self._authorizations[token._nonce] = token
        return token

    def execute(self, order: OrderIntent, authorization: ExecutionAuthorization | None = None) -> TrackedExecution:
        if self.policy.kill_switch:
            self.incident_reporter.report_kill_switch("execution blocked: kill switch is active")
            raise ExecutionSafetyError("execution blocked: kill switch is active")
        if self.policy.mode is ExecutionMode.LIVE and not self.policy.live_trading_enabled:
            raise ExecutionSafetyError("live execution is disabled")

        safe_order = self._validate_order(order)
        if self.policy.mode is ExecutionMode.LIVE:
            self._consume_authorization(safe_order, authorization)

        lifecycle = OrderLifecycle()
        lifecycle.apply(OrderLifecycleEvent(status=OrderStatus.ACCEPTED, timestamp=_now()))
        try:
            result = self.executor.execute(safe_order)
        except Exception as exc:
            lifecycle.apply(OrderLifecycleEvent(status=OrderStatus.REJECTED, timestamp=_now(), reason=str(exc)))
            self.incident_reporter.report_order_rejection(str(exc))
            raise
        return TrackedExecution(result=result, lifecycle=lifecycle)

    def _validate_order(self, order: OrderIntent) -> OrderIntent:
        try:
            safe_order = order.normalized()
            safe_order.validate()
            return safe_order
        except (TypeError, ValueError, OverflowError) as exc:
            raise ExecutionSafetyError(f"execution blocked: invalid order intent: {exc}") from exc

    def _check_reconciliation(self) -> None:
        if not self.policy.reconciliation_enabled:
            return
        if self.position_reader is None or self.local_positions_reader is None:
            self.incident_reporter.report_reconciliation_failure("execution blocked: position reconciliation is not configured")
            raise ExecutionSafetyError("execution blocked: position reconciliation is not configured")
        try:
            PreTradeReconciliationGate(
                PreTradeReconciliationPolicy(enabled=True, block_on_mismatch=True)
            ).check(self.local_positions_reader(), self.position_reader.get_positions())
        except Exception as exc:
            self.incident_reporter.report_reconciliation_failure(str(exc))
            raise ExecutionSafetyError(f"execution blocked: pre-trade reconciliation failed: {exc}") from exc

    def _consume_authorization(self, order: OrderIntent, authorization: ExecutionAuthorization | None) -> None:
        if authorization is None:
            raise ExecutionSafetyError("execution blocked: single-use execution authorization is required")
        stored = self._authorizations.pop(authorization._nonce, None)
        if stored is None or stored != authorization:
            raise ExecutionSafetyError("execution blocked: invalid or already-consumed execution authorization")
        if stored._expires_at < _now():
            raise ExecutionSafetyError("execution blocked: execution authorization expired")
        if stored._order_fingerprint != _fingerprint(order):
            raise ExecutionSafetyError("execution blocked: authorization is bound to a different order")


def _fingerprint(order: OrderIntent) -> str:
    payload = "|".join(
        str(value)
        for value in (
            order.symbol,
            order.side,
            order.price,
            order.stop,
            order.target,
            order.quantity,
            order.risk_amount,
            order.strategy,
            order.confidence,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now():
    return datetime.now(timezone.utc)
