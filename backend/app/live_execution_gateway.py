from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import secrets
from typing import Any, Callable, Protocol

from app.broker_adapter import BrokerOrderRequest, BrokerOrderUpdate
from app.broker_context_attestation import BrokerContextAttestor
from app.broker_execution_context import BrokerExecutionContext
from app.broker_order_lifecycle import OrderLifecycle, OrderLifecycleEvent, OrderStatus
from app.execution_authorization_store import ExecutionAuthorizationStore
from app.order_intent import OrderIntent
from app.pre_trade_reconciliation_gate import PreTradeReconciliationGate, PreTradeReconciliationPolicy
from app.reconciliation_state_store import ReconciliationStateStore
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
    context_max_age_seconds: int = 5
    reconciliation_max_age_seconds: float = 30.0


class BrokerExecutor(Protocol):
    def execute(self, order: OrderIntent): ...


class BrokerPositionReader(Protocol):
    def get_positions(self) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class ExecutionAuthorization:
    """Single-use authorization bound to one normalized order and broker context."""

    _nonce: str
    _order_fingerprint: str
    _context_key: str
    _expires_at: datetime


@dataclass(frozen=True)
class TrackedExecution:
    result: object
    lifecycle: OrderLifecycle


class LiveExecutionGateway:
    """Single safety boundary between approved trade intents and broker execution."""

    def __init__(
        self,
        executor: BrokerExecutor,
        policy: ExecutionPolicy | None = None,
        *,
        position_reader: BrokerPositionReader | None = None,
        local_positions_reader: Callable[[], list[dict[str, Any]]] | None = None,
        incident_reporter: IncidentReporter | None = None,
        authorization_store: ExecutionAuthorizationStore | None = None,
        context_attestor: BrokerContextAttestor | None = None,
        reconciliation_state_store: ReconciliationStateStore | None = None,
    ) -> None:
        self.executor = executor
        self.policy = policy or ExecutionPolicy()
        self.position_reader = position_reader
        self.local_positions_reader = local_positions_reader
        self.incident_reporter = incident_reporter or IncidentReporter()
        self.authorization_store = authorization_store or ExecutionAuthorizationStore()
        self.context_attestor = context_attestor
        self.reconciliation_state_store = reconciliation_state_store

    def authorize(self, order: OrderIntent, context: BrokerExecutionContext) -> ExecutionAuthorization:
        """Validate a live order against current state and a coordinator-attested broker context."""
        if self.policy.kill_switch:
            self.incident_reporter.report_kill_switch("execution blocked: kill switch is active")
            raise ExecutionSafetyError("execution blocked: kill switch is active")
        if self.policy.mode is not ExecutionMode.LIVE:
            raise ExecutionSafetyError("execution authorization is only required for live mode")
        if not self.policy.live_trading_enabled:
            raise ExecutionSafetyError("live execution is disabled")
        if not isinstance(context, BrokerExecutionContext):
            raise ExecutionSafetyError("execution blocked: broker execution context is required")
        if self.context_attestor is None or not self.context_attestor.verify(context):
            raise ExecutionSafetyError("execution blocked: broker execution context is not coordinator-attested")
        self._validate_context_freshness(context)
        safe_order = self._validate_order(order)
        self._check_reconciliation(context)
        ttl = int(self.policy.authorization_ttl_seconds)
        if ttl <= 0:
            raise ExecutionSafetyError("execution authorization TTL must be positive")
        token = ExecutionAuthorization(
            _nonce=secrets.token_urlsafe(32),
            _order_fingerprint=_fingerprint(safe_order),
            _context_key=_context_key(context),
            _expires_at=_now() + timedelta(seconds=ttl),
        )
        try:
            self.authorization_store.issue(token)
        except Exception as exc:
            raise ExecutionSafetyError("execution blocked: authorization could not be persisted") from exc
        return token

    def authorize_request(self, request: BrokerOrderRequest, context: BrokerExecutionContext) -> ExecutionAuthorization:
        self._validate_request_context_identity(request, context)
        return self.authorize(_order_intent_from_request(request), context)

    def execute(
        self,
        order: OrderIntent,
        authorization: ExecutionAuthorization | None = None,
        context: BrokerExecutionContext | None = None,
    ) -> TrackedExecution:
        if self.policy.kill_switch:
            self.incident_reporter.report_kill_switch("execution blocked: kill switch is active")
            raise ExecutionSafetyError("execution blocked: kill switch is active")
        if self.policy.mode is ExecutionMode.LIVE and not self.policy.live_trading_enabled:
            raise ExecutionSafetyError("live execution is disabled")

        safe_order = self._validate_order(order)
        if self.policy.mode is ExecutionMode.LIVE:
            self._consume_authorization(safe_order, authorization, context)

        lifecycle = OrderLifecycle(requested_quantity=safe_order.quantity)
        lifecycle.apply(OrderLifecycleEvent(status=OrderStatus.ACCEPTED, timestamp=_now()))
        try:
            result = self.executor.execute(safe_order)
            self._apply_broker_result(lifecycle, result)
        except Exception as exc:
            if not lifecycle.terminal:
                lifecycle.apply(OrderLifecycleEvent(status=OrderStatus.REJECTED, timestamp=_now(), reason=str(exc)))
            self.incident_reporter.report_order_rejection(str(exc))
            raise
        return TrackedExecution(result=result, lifecycle=lifecycle)

    def execute_request(
        self,
        request: BrokerOrderRequest,
        authorization: ExecutionAuthorization | None = None,
        context: BrokerExecutionContext | None = None,
    ) -> TrackedExecution:
        if self.policy.mode is ExecutionMode.LIVE:
            if not isinstance(context, BrokerExecutionContext):
                raise ExecutionSafetyError("execution blocked: broker execution context is required")
            self._validate_request_context_identity(request, context)
        return self.execute(_order_intent_from_request(request), authorization, context)

    @staticmethod
    def _apply_broker_result(lifecycle: OrderLifecycle, result: object) -> None:
        if not isinstance(result, BrokerOrderUpdate):
            return
        status_map = {
            "NEW": OrderStatus.ACCEPTED,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "REJECTED": OrderStatus.REJECTED,
            "CANCELLED": OrderStatus.CANCELLED,
        }
        try:
            status = status_map[result.status.upper()]
        except (AttributeError, KeyError) as exc:
            raise ExecutionSafetyError("execution blocked: broker returned unsupported lifecycle status") from exc
        filled = result.filled_quantity if result.filled_quantity is not None else 0
        lifecycle.apply(
            OrderLifecycleEvent(
                status=status,
                timestamp=_now(),
                broker_order_id=result.order_id,
                filled_quantity=filled,
                average_price=result.average_price,
                reason=result.message if status in {OrderStatus.REJECTED, OrderStatus.CANCELLED} else None,
            )
        )

    def _validate_order(self, order: OrderIntent) -> OrderIntent:
        try:
            safe_order = order.normalized()
            safe_order.validate()
            return safe_order
        except (TypeError, ValueError, OverflowError) as exc:
            raise ExecutionSafetyError(f"execution blocked: invalid order intent: {exc}") from exc

    def _validate_context_freshness(self, context: BrokerExecutionContext) -> None:
        max_age = int(self.policy.context_max_age_seconds)
        if max_age <= 0:
            raise ExecutionSafetyError("execution context max age must be positive")
        observed_at = context.observed_at
        if observed_at.tzinfo is None:
            raise ExecutionSafetyError("execution blocked: broker execution context timestamp is not timezone-aware")
        age = (_now() - observed_at).total_seconds()
        if age < 0:
            raise ExecutionSafetyError("execution blocked: broker execution context timestamp is in the future")
        if age > max_age:
            raise ExecutionSafetyError("execution blocked: broker execution context is stale")

    @staticmethod
    def _validate_request_context_identity(
        request: BrokerOrderRequest,
        context: BrokerExecutionContext,
    ) -> None:
        if not isinstance(request, BrokerOrderRequest):
            raise ExecutionSafetyError("execution blocked: broker order request is required")
        if request.broker_account_id is None:
            raise ExecutionSafetyError("execution blocked: broker order request account identity is required")
        if request.broker_route is None or not str(request.broker_route).strip():
            raise ExecutionSafetyError("execution blocked: broker order request route identity is required")
        if request.broker_route_generation is None or not str(request.broker_route_generation).strip():
            raise ExecutionSafetyError("execution blocked: broker order request route generation is required")
        if str(request.broker_account_id).strip() != context.account_id:
            raise ExecutionSafetyError("execution blocked: broker order request account does not match execution context")
        if str(request.broker_route).strip() != context.broker_route:
            raise ExecutionSafetyError("execution blocked: broker order request route does not match execution context")
        if str(request.broker_route_generation).strip() != context.route_generation:
            raise ExecutionSafetyError("execution blocked: broker order request route generation does not match execution context")

    def _check_reconciliation(self, context: BrokerExecutionContext) -> None:
        if not self.policy.reconciliation_enabled:
            return
        if self.reconciliation_state_store is None:
            self.incident_reporter.report_reconciliation_failure(
                "execution blocked: durable reconciliation state is not configured"
            )
            raise ExecutionSafetyError("execution blocked: durable reconciliation state is not configured")
        try:
            if self.reconciliation_state_store.is_trading_blocked(
                broker_account_id=context.account_id,
                broker_route=context.broker_route,
                max_age_seconds=self.policy.reconciliation_max_age_seconds,
            ):
                self.incident_reporter.report_reconciliation_failure(
                    "execution blocked: durable reconciliation state is not verified and fresh"
                )
                raise ExecutionSafetyError(
                    "execution blocked: durable reconciliation state is not verified and fresh"
                )
            if self.position_reader is None or self.local_positions_reader is None:
                self.incident_reporter.report_reconciliation_failure(
                    "execution blocked: position reconciliation is not configured"
                )
                raise ExecutionSafetyError("execution blocked: position reconciliation is not configured")
            PreTradeReconciliationGate(
                PreTradeReconciliationPolicy(enabled=True, block_on_mismatch=True)
            ).check(self.local_positions_reader(), self.position_reader.get_positions())
        except ExecutionSafetyError:
            raise
        except Exception as exc:
            self.incident_reporter.report_reconciliation_failure(str(exc))
            raise ExecutionSafetyError(f"execution blocked: pre-trade reconciliation failed: {exc}") from exc

    def _consume_authorization(
        self,
        order: OrderIntent,
        authorization: ExecutionAuthorization | None,
        context: BrokerExecutionContext | None,
    ) -> None:
        if authorization is None:
            raise ExecutionSafetyError("execution blocked: single-use execution authorization is required")
        if not isinstance(authorization, ExecutionAuthorization):
            raise ExecutionSafetyError("execution blocked: invalid execution authorization")
        if not isinstance(context, BrokerExecutionContext):
            raise ExecutionSafetyError("execution blocked: broker execution context is required")
        if self.context_attestor is None or not self.context_attestor.verify(context):
            raise ExecutionSafetyError("execution blocked: broker execution context is not coordinator-attested")
        if authorization._expires_at.tzinfo is None:
            raise ExecutionSafetyError("execution blocked: invalid execution authorization expiry")
        if authorization._order_fingerprint != _fingerprint(order):
            raise ExecutionSafetyError("execution blocked: authorization is bound to a different order")
        if authorization._context_key != _context_key(context):
            raise ExecutionSafetyError("execution blocked: authorization is bound to a different broker context")
        try:
            status = self.authorization_store.consume(
                authorization,
                _fingerprint(order),
                _context_key(context),
                _now,
            )
        except Exception as exc:
            raise ExecutionSafetyError("execution blocked: authorization state could not be verified") from exc
        messages = {
            "missing": "execution blocked: invalid or already-consumed execution authorization",
            "consumed": "execution blocked: invalid or already-consumed execution authorization",
            "order_mismatch": "execution blocked: authorization is bound to a different order",
            "context_mismatch": "execution blocked: authorization is bound to a different broker context",
            "expired": "execution blocked: execution authorization expired",
            "invalid_expiry": "execution blocked: invalid execution authorization expiry",
        }
        if status != "consumed_now":
            raise ExecutionSafetyError(messages.get(status, "execution blocked: invalid execution authorization"))


def _order_intent_from_request(request: BrokerOrderRequest) -> OrderIntent:
    if request.price is None or request.stop is None or request.target is None:
        raise ExecutionSafetyError("execution blocked: AI broker request requires entry, stop, and target")
    risk_amount = abs(float(request.price) - float(request.stop)) * float(request.quantity)
    return OrderIntent(
        symbol=request.symbol,
        side=request.side,
        entry=float(request.price),
        stop_loss=float(request.stop),
        take_profit=float(request.target),
        quantity=float(request.quantity),
        risk_amount=risk_amount,
        source="ai-execution",
        confidence=1.0,
    )


def _fingerprint(order: OrderIntent) -> str:
    payload = "|".join(
        str(value)
        for value in (
            order.symbol,
            order.side,
            order.entry,
            order.stop_loss,
            order.take_profit,
            order.quantity,
            order.risk_amount,
            order.source,
            order.confidence,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _context_key(context: BrokerExecutionContext) -> str:
    return "|".join(str(value) for value in context.canonical_key)


def _now():
    return datetime.now(timezone.utc)
