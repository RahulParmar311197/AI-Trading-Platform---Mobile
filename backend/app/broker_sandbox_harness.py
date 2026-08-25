from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.broker_contracts import BrokerOrderRequest, BrokerOrderResult, BrokerOrderState


@dataclass(frozen=True)
class SandboxTestResult:
    name: str
    passed: bool
    detail: str = ""


class BrokerSandboxHarness:
    """Vendor-neutral contract harness; never submits live orders itself."""

    def __init__(self, submit: Callable[[BrokerOrderRequest], BrokerOrderResult], status: Callable[[str], BrokerOrderResult], cancel: Callable[[str], bool]):
        self.submit_fn = submit
        self.status_fn = status
        self.cancel_fn = cancel

    def run(self, client_order_id: str, symbol: str, quantity: float = 1.0) -> list[SandboxTestResult]:
        if not client_order_id or not symbol or quantity <= 0:
            raise ValueError("client_order_id, symbol and positive quantity are required")
        results: list[SandboxTestResult] = []
        request = BrokerOrderRequest(client_order_id, symbol, "BUY", quantity)
        try:
            placed = self.submit_fn(request)
            ok = placed.client_order_id == client_order_id and placed.state in {BrokerOrderState.ACCEPTED, BrokerOrderState.PENDING, BrokerOrderState.PARTIAL, BrokerOrderState.FILLED}
            results.append(SandboxTestResult("place_order", ok, placed.state.value))
            if not placed.broker_order_id:
                results.append(SandboxTestResult("broker_order_id", False, "missing broker order id"))
                return results
            current = self.status_fn(placed.broker_order_id)
            results.append(SandboxTestResult("status_query", current.broker_order_id == placed.broker_order_id, current.state.value))
            cancelled = self.cancel_fn(placed.broker_order_id)
            results.append(SandboxTestResult("cancel_order", cancelled, "cancel requested" if cancelled else "cancel rejected"))
        except Exception as exc:
            results.append(SandboxTestResult("sandbox_transport", False, str(exc)))
        return results
