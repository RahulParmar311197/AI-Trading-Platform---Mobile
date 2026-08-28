import pytest

from app.broker_adapter import PaperBrokerAdapter
from app.broker_context_attestation import BrokerContextAttestor
from app.broker_factory import build_broker_router
from app.broker_router import BrokerRoute, BrokerRouter
from app.safety_state import SafetyStateStore


SECRET = b"router-reconciliation-attestation-secret-32+"


def test_authoritative_router_reconciliation_produces_attested_context(tmp_path):
    attestor = BrokerContextAttestor(SECRET)
    router = BrokerRouter(
        [BrokerRoute("paper", PaperBrokerAdapter(), broker_account_id=7, generation="account:7:g1")],
        "paper",
        safety_store=SafetyStateStore(str(tmp_path / "safety.json")),
        context_attestor=attestor,
    )

    result = router.reconcile_authoritative([], [], route="paper")

    assert result.ok is True
    assert result.context is not None
    assert attestor.verify(result.context)
    assert result.context.account_id == "7"
    assert result.context.broker_route == "paper"
    assert result.context.route_generation == "account:7:g1"


def test_authoritative_router_reconciliation_fails_closed_without_attestor(tmp_path):
    router = BrokerRouter(
        [BrokerRoute("paper", PaperBrokerAdapter(), broker_account_id=7, generation="account:7:g1")],
        "paper",
        safety_store=SafetyStateStore(str(tmp_path / "safety.json")),
    )

    with pytest.raises(RuntimeError, match="canonical broker context attestor"):
        router.reconcile_authoritative([], [], route="paper")


def test_build_broker_router_preserves_canonical_attestor():
    attestor = BrokerContextAttestor(SECRET)
    router = build_broker_router(SafetyStateStore(), context_attestor=attestor)
    assert router.context_attestor is attestor
