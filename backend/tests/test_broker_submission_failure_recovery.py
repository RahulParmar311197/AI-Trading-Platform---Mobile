from datetime import timedelta

import pytest

from app.broker_adapter import BrokerOrderRequest, PaperBrokerAdapter
from app.broker_router import BrokerRoute, BrokerRouter
from app.reconciliation_result import ReconciliationResult
from app.safety_state import SafetyStateStore


class FailingPaperBroker(PaperBrokerAdapter):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode

    def submit_order(self, order):
        if self.mode == "recover":
            self._orders["PAPER-RECOVERED"] = {
                "order_id": "PAPER-RECOVERED", "broker_order_id": "PAPER-RECOVERED",
                "client_order_id": order.client_order_id, "symbol": order.symbol,
                "side": order.side, "quantity": order.quantity, "filled_quantity": 0,
                "status": "NEW",
            }
        elif self.mode == "ambiguous":
            for oid in ("PAPER-A", "PAPER-B"):
                self._orders[oid] = {
                    "order_id": oid, "broker_order_id": oid,
                    "client_order_id": order.client_order_id, "symbol": order.symbol,
                    "side": order.side, "quantity": order.quantity, "filled_quantity": 0,
                    "status": "NEW",
                }
        raise TimeoutError("broker response lost")


def _ready_router(tmp_path, broker):
    store = SafetyStateStore(str(tmp_path / "safety.json"))
    router = BrokerRouter([BrokerRoute("paper", broker)], "paper", safety_store=store)
    halted = store.halt("reconcile")
    fingerprint = router._current_snapshot_fingerprint(router.get("paper"))
    result = ReconciliationResult.from_verified_state(
        account_id="paper", generation=1,
        reconciled_at=halted.halted_at + timedelta(seconds=0.001),
        open_orders_reconciled=True, positions_reconciled=True,
        submission_intents_resolved=0, broker_ready=True,
        broker_snapshot_fingerprint=fingerprint,
    )
    store.clear(result)
    return router, store


def test_lost_submit_response_recovers_existing_broker_order(tmp_path):
    router, store = _ready_router(tmp_path, FailingPaperBroker("recover"))
    result = router.submit(BrokerOrderRequest("c1", "NIFTY", "BUY", 1))
    assert result.order_id == "PAPER-RECOVERED"
    assert result.message == "BROKER_SUBMISSION_RECOVERED"
    assert store.load().trading_halted is False


def test_ambiguous_lost_submit_response_halts_trading(tmp_path):
    router, store = _ready_router(tmp_path, FailingPaperBroker("ambiguous"))
    with pytest.raises(RuntimeError, match="outcome is unknown"):
        router.submit(BrokerOrderRequest("c1", "NIFTY", "BUY", 1))
    state = store.load()
    assert state.trading_halted is True
    assert "ambiguous broker submission" in (state.halt_reason or "")
