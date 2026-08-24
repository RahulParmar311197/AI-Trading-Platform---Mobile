from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from app.order_lifecycle import OrderLifecycle
from app.order_reconciliation import BrokerOrder, OrderReconciler, ReconciliationEvent


@dataclass(frozen=True)
class BrokerPosition:
    symbol: str
    side: str
    quantity: float
    entry_price: float


@dataclass(frozen=True)
class RecoveryReport:
    order_events: list[ReconciliationEvent]
    position_mismatches: list[str]
    safe_to_resume: bool


class ExecutionRecovery:
    """Reconcile broker state before allowing the execution engine to resume."""

    def __init__(self, lifecycle: OrderLifecycle):
        self.lifecycle = lifecycle

    @staticmethod
    def _validate_broker_positions(
        broker_positions: list[BrokerPosition],
    ) -> dict[str, BrokerPosition]:
        remote: dict[str, BrokerPosition] = {}
        for position in broker_positions:
            symbol = str(position.symbol).strip().upper()
            side = str(position.side).strip().upper()
            quantity = float(position.quantity)
            entry_price = float(position.entry_price)
            if not symbol:
                raise ValueError("broker position missing symbol")
            if side not in {"BUY", "SELL"}:
                raise ValueError(f"invalid broker position side: {symbol}")
            if not isfinite(quantity) or quantity < 0:
                raise ValueError(f"invalid broker position quantity: {symbol}")
            if quantity > 0 and (not isfinite(entry_price) or entry_price <= 0):
                raise ValueError(f"invalid broker position entry price: {symbol}")
            if symbol in remote:
                raise ValueError(f"duplicate broker position: {symbol}")
            remote[symbol] = BrokerPosition(symbol, side, quantity, entry_price)
        return remote

    def recover(
        self,
        broker_orders: list[BrokerOrder],
        broker_positions: list[BrokerPosition],
    ) -> RecoveryReport:
        events = OrderReconciler(self.lifecycle).reconcile(broker_orders)
        remote = self._validate_broker_positions(broker_positions)
        mismatches: list[str] = []
        local = {
            str(symbol).strip().upper(): position
            for symbol, position in self.lifecycle.positions.items()
            if getattr(position, "status", "OPEN") == "OPEN" and position.quantity > 0
        }

        # Compare signed exposure. Broker-only exposure is a hard startup drift,
        # never something recovery may silently overwrite with local state.
        for symbol in sorted(set(local) | set(remote)):
            local_position = local.get(symbol)
            remote_position = remote.get(symbol)
            if local_position is None:
                if remote_position.quantity > 0:
                    mismatches.append(f"{symbol}:BROKER_ONLY_POSITION")
                continue
            if remote_position is None:
                mismatches.append(f"{symbol}:POSITION_MISSING_ON_BROKER")
                continue

            local_side = str(local_position.side).upper()
            remote_side = remote_position.side
            local_quantity = float(local_position.quantity)
            remote_quantity = float(remote_position.quantity)
            local_signed = local_quantity if local_side == "BUY" else -local_quantity
            remote_signed = remote_quantity if remote_side == "BUY" else -remote_quantity
            if local_signed != remote_signed:
                mismatches.append(f"{symbol}:POSITION_STATE_MISMATCH")
                continue
            if abs(float(local_position.entry_price) - remote_position.entry_price) > 1e-6:
                mismatches.append(f"{symbol}:POSITION_ENTRY_PRICE_MISMATCH")

        safe_to_resume = (
            not mismatches
            and not any(event.action.value == "ALERT" for event in events)
        )
        return RecoveryReport(events, mismatches, safe_to_resume)
