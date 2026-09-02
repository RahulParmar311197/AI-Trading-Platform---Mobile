from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.ai_decision_engine import TradingDecision
from app.ai_execution_orchestrator import AIRiskSnapshot, AIExecutionOrchestrator
from app.broker_execution_context import BrokerExecutionContext
from app.broker_order_lifecycle import OrderStatus
from app.instruments import InstrumentProvider, InstrumentSpec


class FakeDecisionEngine:
    def __init__(self, decision):
        self.decision = decision

    def decide(self, context, *, prediction=None, ml_confidence=0.0, confluence=None):
        return self.decision


class FakeProvider(InstrumentProvider):
    def resolve(self, symbol):
        if symbol != "NIFTY":
            return None
        return InstrumentSpec(
            symbol="NIFTY", security_id="NIFTY-TEST", exchange_segment="NSE_FO",
            lot_size=50, tick_size=0.05, multiplier=1.0, tradable=True,
        )


class FakeSubmitter:
    def __init__(self, lifecycle=None):
        self.requests = []
        self.authorized_requests = []
        self.executions = []
        self.lifecycle = lifecycle

    def authorize_request(self, request, context):
        self.authorized_requests.append((request, context))
        return "authorization-token"

    def execute_request(self, request, authorization, context):
        self.executions.append((request, authorization, context))
        self.requests.append(request)
        if self.lifecycle is not None:
            return SimpleNamespace(lifecycle=self.lifecycle)
        return {"status": "accepted"}


class FakeReservationStore:
    def __init__(self, reconcile_result="RELEASED"):
        self.reconcile_result = reconcile_result
        self.reserved = []
        self.released = []
        self.reconciled = []

    def reserve(self, **kwargs):
        self.reserved.append(kwargs)
        return "reservation-1"

    def release(self, reservation_id):
        self.released.append(reservation_id)

    def reconcile_client_order(self, **kwargs):
        self.reconciled.append(kwargs)
        return self.reconcile_result


class LegacySubmitter:
    async def submit(self, request):
        return {"status": "accepted"}


def make_decision(side="BUY"):
    return TradingDecision(
        symbol="NIFTY", decision=side, confidence=0.9,
        entry=100.0, stop_loss=90.0 if side == "BUY" else 110.0,
        target=120.0 if side == "BUY" else 80.0, reasons=("test",),
    )


def risk_snapshot(**overrides):
    values = dict(daily_pnl=0.0, open_positions=0, recent_losses=0, snapshot_fingerprint="snapshot-1")
    values.update(overrides)
    return AIRiskSnapshot(**values)


def broker_context(**overrides):
    values = dict(
        account_id="acct-1",
        broker_route="route-1",
        route_generation="route-gen-1",
        generation=7,
        snapshot_fingerprint="snapshot-1",
        observed_at=datetime.now(timezone.utc),
    )
    values.update(overrides)
    return BrokerExecutionContext(**values)


def make_orchestrator(submitter, risk_store=None):
    return AIExecutionOrchestrator(
        decision_engine=FakeDecisionEngine(make_decision()),
        instrument_provider=FakeProvider(), order_submitter=submitter,
        risk_reservation_store=risk_store,
    )


@pytest.mark.asyncio
async def test_buy_reaches_authorized_gateway_exactly_once_after_risk_approval():
    submitter = FakeSubmitter()
    context = broker_context()
    result = await make_orchestrator(submitter).evaluate_and_execute(
        object(), equity=100_000, client_order_id="ai-test-1",
        risk_snapshot=risk_snapshot(), broker_execution_context=context,
    )
    assert result.order_request is not None
    assert result.execution == {"status": "accepted"}
    assert result.risk_decision is not None and result.risk_decision.allowed
    assert len(submitter.authorized_requests) == 1
    assert len(submitter.executions) == 1
    assert submitter.executions[0][1] == "authorization-token"
    assert submitter.executions[0][2] is context
    assert submitter.requests[0].quantity == 100


@pytest.mark.asyncio
async def test_opaque_account_identity_is_preserved_to_authorized_gateway():
    submitter = FakeSubmitter()
    context = broker_context(account_id="001")
    result = await make_orchestrator(submitter).evaluate_and_execute(
        object(), equity=100_000, client_order_id="ai-account-1",
        broker_account_id="001", risk_snapshot=risk_snapshot(),
        broker_execution_context=context,
    )
    assert result.order_request is not None
    assert result.order_request.broker_account_id == "001"
    assert submitter.authorized_requests[0][0].broker_account_id == "001"


@pytest.mark.asyncio
async def test_numeric_alias_account_cannot_cross_authorization_context():
    submitter = FakeSubmitter()
    with pytest.raises(RuntimeError, match="broker account identity"):
        await make_orchestrator(submitter).evaluate_and_execute(
            object(), equity=100_000, client_order_id="ai-account-alias",
            broker_account_id="1", risk_snapshot=risk_snapshot(),
            broker_execution_context=broker_context(account_id="001"),
        )
    assert submitter.authorized_requests == []
    assert submitter.executions == []


@pytest.mark.asyncio
async def test_mismatched_risk_snapshot_fingerprint_blocks_before_gateway():
    submitter = FakeSubmitter()
    with pytest.raises(RuntimeError, match="risk snapshot does not match broker execution context"):
        await make_orchestrator(submitter).evaluate_and_execute(
            object(), equity=100_000, client_order_id="ai-snapshot-mismatch",
            risk_snapshot=risk_snapshot(snapshot_fingerprint="snapshot-old"),
            broker_execution_context=broker_context(snapshot_fingerprint="snapshot-new"),
        )
    assert submitter.authorized_requests == []
    assert submitter.executions == []


@pytest.mark.asyncio
async def test_missing_risk_snapshot_fingerprint_blocks_before_gateway():
    submitter = FakeSubmitter()
    with pytest.raises(RuntimeError, match="risk snapshot fingerprint"):
        await make_orchestrator(submitter).evaluate_and_execute(
            object(), equity=100_000, client_order_id="ai-snapshot-missing",
            risk_snapshot=risk_snapshot(snapshot_fingerprint=""),
            broker_execution_context=broker_context(),
        )
    assert submitter.authorized_requests == []
    assert submitter.executions == []


@pytest.mark.asyncio
async def test_risk_rejection_never_reaches_authorized_gateway():
    submitter = FakeSubmitter()
    result = await make_orchestrator(submitter).evaluate_and_execute(
        object(), equity=100_000, client_order_id="ai-test-risk-veto",
        risk_snapshot=risk_snapshot(daily_pnl=-3_000), broker_execution_context=broker_context(),
    )
    assert result.execution is None
    assert result.risk_decision is not None and not result.risk_decision.allowed
    assert submitter.authorized_requests == []
    assert submitter.executions == []


@pytest.mark.asyncio
async def test_trade_requires_authoritative_risk_snapshot():
    submitter = FakeSubmitter()
    with pytest.raises(RuntimeError, match="risk snapshot"):
        await make_orchestrator(submitter).evaluate_and_execute(
            object(), equity=100_000, client_order_id="ai-test-missing-risk"
        )
    assert submitter.authorized_requests == []


@pytest.mark.asyncio
async def test_trade_requires_broker_execution_context():
    submitter = FakeSubmitter()
    with pytest.raises(RuntimeError, match="broker execution context"):
        await make_orchestrator(submitter).evaluate_and_execute(
            object(), equity=100_000, client_order_id="ai-test-missing-context",
            risk_snapshot=risk_snapshot(),
        )
    assert submitter.authorized_requests == []


@pytest.mark.asyncio
async def test_hold_never_reaches_gateway_or_requires_risk_snapshot():
    submitter = FakeSubmitter()
    orchestrator = AIExecutionOrchestrator(
        decision_engine=FakeDecisionEngine(
            TradingDecision(symbol="NIFTY", decision="HOLD", confidence=0.9,
                            entry=None, stop_loss=None, target=None, reasons=("hold",))
        ),
        instrument_provider=FakeProvider(), order_submitter=submitter,
    )
    result = await orchestrator.evaluate_and_execute(
        object(), equity=100_000, client_order_id="ai-test-2"
    )
    assert result.order_request is None
    assert result.execution is None
    assert result.risk_decision is None
    assert submitter.authorized_requests == []
    assert submitter.executions == []


@pytest.mark.asyncio
async def test_risk_approved_trade_rejects_legacy_submitter_without_safety_boundary():
    with pytest.raises(RuntimeError, match="authorized execution gateway"):
        await make_orchestrator(LegacySubmitter()).evaluate_and_execute(
            object(), equity=100_000, client_order_id="ai-test-legacy",
            risk_snapshot=risk_snapshot(), broker_execution_context=broker_context(),
        )


@pytest.mark.asyncio
async def test_terminal_reconciliation_must_release_risk_reservation():
    reservation_store = FakeReservationStore(reconcile_result="ACTIVE")
    lifecycle = SimpleNamespace(status=OrderStatus.FILLED, filled_quantity=100.0)
    submitter = FakeSubmitter(lifecycle=lifecycle)

    with pytest.raises(RuntimeError, match="risk reservation reconciliation"):
        await make_orchestrator(submitter, reservation_store).evaluate_and_execute(
            object(), equity=100_000, client_order_id="ai-terminal-reconcile-mismatch",
            risk_snapshot=risk_snapshot(), broker_execution_context=broker_context(),
        )

    assert reservation_store.reconciled == [{
        "client_order_id": "ai-terminal-reconcile-mismatch",
        "broker_status": "FILLED",
        "remaining_amount": 0.0,
    }]


@pytest.mark.asyncio
async def test_terminal_reconciliation_missing_result_keeps_reservation_held():
    reservation_store = FakeReservationStore(reconcile_result=None)
    lifecycle = SimpleNamespace(status=OrderStatus.CANCELLED, filled_quantity=0.0)
    submitter = FakeSubmitter(lifecycle=lifecycle)

    with pytest.raises(RuntimeError, match="risk reservation reconciliation"):
        await make_orchestrator(submitter, reservation_store).evaluate_and_execute(
            object(), equity=100_000, client_order_id="ai-terminal-reconcile-missing",
            risk_snapshot=risk_snapshot(), broker_execution_context=broker_context(),
        )

    assert reservation_store.released == []


@pytest.mark.asyncio
async def test_partial_fill_requires_active_reservation_when_exposure_remains():
    reservation_store = FakeReservationStore(reconcile_result="RELEASED")
    lifecycle = SimpleNamespace(status=OrderStatus.PARTIALLY_FILLED, filled_quantity=50.0)
    submitter = FakeSubmitter(lifecycle=lifecycle)

    with pytest.raises(RuntimeError, match="risk reservation reconciliation"):
        await make_orchestrator(submitter, reservation_store).evaluate_and_execute(
            object(), equity=100_000, client_order_id="ai-partial-reconcile-mismatch",
            risk_snapshot=risk_snapshot(), broker_execution_context=broker_context(),
        )

    assert reservation_store.reconciled[0]["broker_status"] == "PARTIALLY_FILLED"
    assert reservation_store.reconciled[0]["remaining_amount"] == 5000.0
