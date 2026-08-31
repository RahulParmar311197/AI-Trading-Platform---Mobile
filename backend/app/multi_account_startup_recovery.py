from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.broker_context_attestation import BrokerContextAttestor
from app.broker_execution_context import BrokerExecutionContext
from app.broker_router import BrokerRouter
from app.broker_snapshot import BrokerSnapshot
from app.models.broker_account import BrokerAccount
from app.execution_persistence import ExecutionStateStore
from app.order_lifecycle import OrderLifecycle
from app.reconciliation_coordinator import ReconciliationCoordinator
from app.reconciliation_result import ReconciliationResult
from app.safety_state import SafetyStateStore


@dataclass(frozen=True)
class AccountRecoveryResult:
    account_id: str
    route: str
    ready: bool
    reconciliation: ReconciliationResult | None
    reason: str


@dataclass(frozen=True)
class MultiAccountRecoveryResult:
    ready: bool
    accounts: tuple[AccountRecoveryResult, ...]
    reason: str


class MultiAccountStartupRecovery:
    """Reconcile every active broker account independently, then release the global safety gate."""

    def __init__(self, router: BrokerRouter, execution_store: ExecutionStateStore, safety_store: SafetyStateStore, context_attestor: BrokerContextAttestor | None) -> None:
        self.router = router
        self.execution_store = execution_store
        self.safety_store = safety_store
        self.context_attestor = context_attestor

    @staticmethod
    def _orders_for_account(lifecycle: OrderLifecycle, account_id: str) -> list[dict[str, Any]]:
        return [{"client_order_id": order_id, "status": record.status.value, "quantity": record.quantity, "filled_quantity": record.filled_quantity} for order_id, record in lifecycle.orders.items() if str(record.broker_account_id or "") == account_id]

    @staticmethod
    def _positions_for_account(lifecycle: OrderLifecycle, account_id: str) -> list[dict[str, Any]]:
        return [{"symbol": position.symbol, "quantity": position.quantity} for position in lifecycle.positions.values() if str(getattr(position, "broker_account_id", "") or "") == account_id]

    def run(self, lifecycle: OrderLifecycle, accounts: list[BrokerAccount]) -> MultiAccountRecoveryResult:
        if len(accounts) < 2:
            raise ValueError("multi-account recovery requires at least two active accounts")
        if self.context_attestor is None:
            return MultiAccountRecoveryResult(False, (), "BROKER_CONTEXT_ATTESTOR_REQUIRED")
        self.execution_store.load(lifecycle)
        ambiguous_orders = [oid for oid, order in lifecycle.orders.items() if not str(order.broker_account_id or "").strip()]
        ambiguous_positions = [symbol for symbol, position in lifecycle.positions.items() if not str(getattr(position, "broker_account_id", "") or "").strip()]
        if ambiguous_orders or ambiguous_positions:
            return MultiAccountRecoveryResult(False, (), "MULTI_ACCOUNT_STATE_UNSCOPED: every persisted order and position must have a broker account id")

        results: list[AccountRecoveryResult] = []
        verified: list[tuple[ReconciliationResult, BrokerExecutionContext]] = []
        for account in accounts:
            account_id = str(account.id)
            route = f"{account.broker}:account:{account.id}"
            try:
                selected = self.router.get(route)
                if selected.broker_account_id is None or str(selected.broker_account_id) != account_id:
                    raise RuntimeError("broker route account binding mismatch")
                if selected.generation is None:
                    raise RuntimeError("broker route generation is missing")
                snapshot = self.router.get_snapshot(route)
                if not isinstance(snapshot, BrokerSnapshot):
                    raise RuntimeError("authoritative broker snapshot is required")
                coordinator = ReconciliationCoordinator(engine=self.router.reconciliation_engine, route=selected.name, account_id=account_id, route_generation=str(selected.generation), context_attestor=self.context_attestor, generation=self.router._next_reconciliation_generation(selected))
                result = coordinator.reconcile(internal_orders=self._orders_for_account(lifecycle, account_id), internal_positions=self._positions_for_account(lifecycle, account_id), broker_snapshot=snapshot, broker_ready=True)
                verified.append((result, result.context))
                results.append(AccountRecoveryResult(account_id, route, True, result, "RECOVERY_OK"))
            except Exception as exc:
                results.append(AccountRecoveryResult(account_id, route, False, None, f"RECOVERY_FAILED: {type(exc).__name__}"))

        if len(results) != len(accounts) or not all(item.ready for item in results):
            self.safety_store.halt("MULTI_ACCOUNT_RECONCILIATION_FAILED")
            return MultiAccountRecoveryResult(False, tuple(results), "MULTI_ACCOUNT_RECONCILIATION_FAILED")
        try:
            self.safety_store.clear_all(verified)
        except Exception as exc:
            self.safety_store.halt(f"MULTI_ACCOUNT_SAFETY_CLEAR_FAILED: {type(exc).__name__}")
            return MultiAccountRecoveryResult(False, tuple(results), "MULTI_ACCOUNT_SAFETY_CLEAR_FAILED")
        return MultiAccountRecoveryResult(True, tuple(results), "RECOVERY_OK")
