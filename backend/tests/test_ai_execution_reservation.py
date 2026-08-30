from datetime import datetime, timezone

import pytest

from app.ai_decision_engine import TradingDecision
from app.ai_execution_orchestrator import AIRiskSnapshot, AIExecutionOrchestrator
from app.broker_execution_context import BrokerExecutionContext
from app.broker_order_lifecycle import OrderLifecycle, OrderLifecycleEvent, OrderStatus
from app.instruments import InstrumentProvider, InstrumentSpec


class DecisionEngine:
    def decide(self, context, *, prediction=None, ml_confidence=0.0, confluence=None):
        return TradingDecision(
            symbol="NIFTY", decision="BUY", confidence=0.9, entry=100.0,
            stop_loss=90.0, target=120.0, reasons=("test",),
        )


class Provider(InstrumentProvider):
    def resolve(self, symbol):
        return InstrumentSpec(
            symbol=symbol, security_id="NIFTY-TEST", exchange_segment="NSE_FO",
            lot_size=50, tick_size=0.05, multiplier=1.0, tradable=True,
        )


class ReservationStore:
    def __init__(self):
        self.calls = []
        self.released = []

    def reserve(self, **kwargs):
        self.calls.append(kwargs)
        return "reservation-1"

    def release(self, reservation_id):
        self.released.append(reservation_id)


class Submitter:
    def __init__(self, status=OrderStatus.ACCEPTED):
        self.status = status
        self.events = []

    def authorize_request(self, request, context):
        self.events.append("authorize")
        return "auth"

    def execute_request(self, request, authorization, context):
        self.events.append("execute")
        lifecycle = OrderLifecycle(requested_quantity=request.quantity)
        lifecycle.apply(OrderLifecycleEvent(status=OrderStatus.ACCEPTED, timestamp=datetime.now(timezone.utc)))
        if self.status is not OrderStatus.ACCEPTED:
            lifecycle.apply(OrderLifecycleEvent(status=self.status, timestamp=datetime.now(timezone.utc)))
        return type("Tracked", (), {"lifecycle": lifecycle})()


class RejectingAuthorize(Submitter):
    def authorize_request(self, request, context):
        self.events.append("authorize")
        raise RuntimeError("authorization failed")


def context():
    return BrokerExecutionContext(
        account_id="001", broker_route="upstox", route_generation="gen-1",
        generation=1, snapshot_fingerprint="snapshot-1", observed_at=datetime.now(timezone.utc),
    )


def snapshot():
    return AIRiskSnapshot(
        daily_pnl=0, open_positions=0, current_exposure=0,
        snapshot_fingerprint="snapshot-1",
    )


def orchestrator(submitter, reservations):
    return AIExecutionOrchestrator(
        decision_engine=DecisionEngine(), instrument_provider=Provider(),
        order_submitter=submitter, risk_reservation_store=reservations,
    )


@pytest.mark.asyncio
async def test_reservation_is_acquired_before_authorization():
    reservations = ReservationStore()
    submitter = Submitter()
    result = await orchestrator(submitter, reservations).evaluate_and_execute(
        object(), equity=100_000, client_order_id="reservation-1",
        broker_account_id="001", broker_route="upstox", broker_route_generation="gen-1",
        risk_snapshot=snapshot(), broker_execution_context=context(),
    )
    assert result.risk_reservation_id == "reservation-1"
    assert reservations.calls[0]["broker_account_id"] == "001"
    assert reservations.calls[0]["amount"] == 10_000
    assert submitter.events == ["authorize", "execute"]


@pytest.mark.asyncio
async def test_authorization_failure_releases_reservation_before_broker_execution():
    reservations = ReservationStore()
    submitter = RejectingAuthorize()
    with pytest.raises(RuntimeError, match="authorization failed"):
        await orchestrator(submitter, reservations).evaluate_and_execute(
            object(), equity=100_000, client_order_id="reservation-2",
            broker_account_id="001", broker_route="upstox", broker_route_generation="gen-1",
            risk_snapshot=snapshot(), broker_execution_context=context(),
        )
    assert reservations.released == ["reservation-1"]
    assert submitter.events == ["authorize"]


@pytest.mark.asyncio
async def test_terminal_rejection_releases_reservation():
    reservations = ReservationStore()
    submitter = Submitter(status=OrderStatus.REJECTED)
    result = await orchestrator(submitter, reservations).evaluate_and_execute(
        object(), equity=100_000, client_order_id="reservation-3",
        broker_account_id="001", broker_route="upstox", broker_route_generation="gen-1",
        risk_snapshot=snapshot(), broker_execution_context=context(),
    )
    assert result.risk_reservation_id is None
    assert reservations.released == ["reservation-1"]
