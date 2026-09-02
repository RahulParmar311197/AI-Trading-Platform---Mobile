from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.broker_adapter import BrokerOrderRequest
from app.db import Base
from app.models.submission_intent import SubmissionIntentRecord
from app.submission_intent_store import SubmissionIntentStore
from app.submission_recovery import SubmissionRecoveryError, recover_submission


class FakeBroker:
    def __init__(self):
        self.get_order_calls: list[str] = []
        self.find_calls: list[str] = []
        self.orders: dict[str, dict] = {}

    def get_order(self, broker_order_id: str):
        self.get_order_calls.append(broker_order_id)
        return dict(self.orders[broker_order_id])

    def find_order_by_client_id(self, client_order_id: str):
        self.find_calls.append(client_order_id)
        for order in self.orders.values():
            if order.get("client_order_id") == client_order_id:
                return dict(order)
        return None


class NoClientIdLookupBroker:
    pass


def _store(tmp_path: Path) -> SubmissionIntentStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'recovery.db'}")
    Base.metadata.create_all(engine, tables=[SubmissionIntentRecord.__table__])
    return SubmissionIntentStore(session_factory=sessionmaker(bind=engine, autoflush=False, autocommit=False))


def _request() -> BrokerOrderRequest:
    return BrokerOrderRequest(
        client_order_id="cli-1",
        symbol="NIFTY",
        side="BUY",
        quantity=10,
        broker_account_id="001",
        broker_route="upstox",
        broker_route_generation="gen-1",
    )


def _filled(order_id: str) -> dict:
    return {
        "order_id": order_id,
        "client_order_id": "cli-1",
        "symbol": "NIFTY",
        "side": "BUY",
        "quantity": 10,
        "filled_quantity": 10,
        "average_price": 100,
        "status": "FILLED",
        "broker_account_id": "001",
        "broker_route": "upstox",
        "broker_route_generation": "gen-1",
    }


def test_bound_broker_order_is_authoritative_after_restart(tmp_path: Path):
    store = _store(tmp_path)
    store.create(
        client_order_id="cli-1", route="upstox", account_id="001", symbol="NIFTY",
        side="BUY", quantity=10, request_fingerprint="fp-1",
    )
    store.record_broker_order("cli-1", "broker-99", "NEW")
    broker = FakeBroker()
    broker.orders["broker-99"] = _filled("broker-99")

    result = recover_submission(_request(), executor=broker, intent_store=_store(tmp_path))

    assert result is not None
    assert result.order_id == "broker-99"
    assert broker.get_order_calls == ["broker-99"]
    assert broker.find_calls == []


def test_bound_order_failure_does_not_fallback_to_client_id(tmp_path: Path):
    store = _store(tmp_path)
    store.create(
        client_order_id="cli-1", route="upstox", account_id="001", symbol="NIFTY",
        side="BUY", quantity=10, request_fingerprint="fp-1",
    )
    store.record_broker_order("cli-1", "broker-99", "NEW")
    broker = FakeBroker()
    broker.orders["broker-100"] = _filled("broker-100")

    with pytest.raises(SubmissionRecoveryError, match="durable broker order recovery failed"):
        recover_submission(_request(), executor=broker, intent_store=_store(tmp_path))

    assert broker.get_order_calls == ["broker-99"]
    assert broker.find_calls == []


def test_unbound_intent_requires_authoritative_client_id_lookup(tmp_path: Path):
    store = _store(tmp_path)
    store.create(
        client_order_id="cli-1", route="upstox", account_id="001", symbol="NIFTY",
        side="BUY", quantity=10, request_fingerprint="fp-1",
    )

    with pytest.raises(SubmissionRecoveryError, match="requires authoritative client-order-id lookup capability"):
        recover_submission(_request(), executor=NoClientIdLookupBroker(), intent_store=store)

    intent = store.get_unresolved("cli-1")
    assert intent is not None
    assert intent.broker_order_id is None


def test_unbound_intent_establishes_binding_from_exact_client_id_match(tmp_path: Path):
    store = _store(tmp_path)
    store.create(
        client_order_id="cli-1", route="upstox", account_id="001", symbol="NIFTY",
        side="BUY", quantity=10, request_fingerprint="fp-1",
    )
    broker = FakeBroker()
    broker.orders["broker-99"] = _filled("broker-99")

    result = recover_submission(_request(), executor=broker, intent_store=store)

    assert result is not None
    assert result.order_id == "broker-99"
    assert broker.find_calls == ["cli-1"]
    assert store.get_unresolved("cli-1") is None
