from datetime import datetime, timezone

import pytest

from app.ai_decision_engine import TradingDecision
from app.ai_execution_orchestrator import AIRiskSnapshot, AIExecutionOrchestrator
from app.broker_execution_context import BrokerExecutionContext
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
    def __init__(self):
        self.requests = []
        self.authorized_requests = []
        self.executions = []

    def authorize_request(self, request, context):
        self.authorized_requests.append((request, context))
        return "authorization-token"

    def execute_request(self, request, authorization, context):
        self.executions.append((request, authorization, context))
        self.requests.append(request)
        return {"status": "accepted"}


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
    values = dict(daily_pnl=0.0, open_positions=0, recent_losses=0)
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


def make_orchestrator(submitter):
    return AIExecutionOrchestrator(
        decision_engine=FakeDecisionEngine(make_decision()),
        instrument_provider=FakeProvider(), order_submitter=submitter,
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
