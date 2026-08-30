from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.authoritative_live_execution_gateway import AuthoritativeLiveExecutionGateway
from app.broker_adapter import BrokerOrderRequest
from app.broker_order_lifecycle import OrderStatus
from app.db import Base
from app.models.submission_intent import SubmissionIntentRecord
from app.submission_intent_store import SubmissionIntentStore
from app.live_execution_gateway import ExecutionSafetyError


class RestartRecoveryBroker:
    def __init__(self) -> None:
        self.submit_calls = 0
        self.get_calls: list[str] = []
        self.find_calls: list[str] = []
        self.orders = {
            "broker-99": {
                "order_id": "broker-99",
                "client_order_id": "client-1",
                "symbol": "NIFTY",
                "side": "BUY",
                "quantity": 1,
                "filled_quantity": 1,
                "average_price": 100,
                "status": "FILLED",
                "broker_account_id": "acct-1",
                "broker_route": "upstox",
                "broker_route_generation": "gen-1",
            }
        }

    def execute(self, order):
        self.submit_calls += 1
        raise TimeoutError("transport timeout after broker accepted order")

    def get_order(self, broker_order_id: str):
        self.get_calls.append(broker_order_id)
        if broker_order_id not in self.orders:
            raise KeyError(broker_order_id)
        return dict(self.orders[broker_order_id])

    def find_order_by_client_id(self, client_order_id: str):
        self.find_calls.append(client_order_id)
        raise AssertionError("client-id fallback must not run after durable broker binding")


def _store(tmp_path: Path) -> SubmissionIntentStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'submission.db'}")
    Base.metadata.create_all(engine, tables=[SubmissionIntentRecord.__table__])
    return SubmissionIntentStore(
        session_factory=sessionmaker(bind=engine, autoflush=False, autocommit=False)
    )


def _request() -> BrokerOrderRequest:
    return BrokerOrderRequest(
        client_order_id="client-1",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        price=100,
        stop=99,
        target=102,
        broker_account_id="acct-1",
        broker_route="upstox",
        broker_route_generation="gen-1",
    )


def test_gateway_uses_durable_broker_binding_after_restart_without_client_id_fallback(tmp_path: Path):
    first_store = _store(tmp_path)
    first_store.create(
        client_order_id="client-1",
        route="upstox",
        account_id="acct-1",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        request_fingerprint="fp-1",
    )
    first_store.record_broker_order("client-1", "broker-99", "NEW")

    broker = RestartRecoveryBroker()
    restarted_store = _store(tmp_path)
    gateway = AuthoritativeLiveExecutionGateway(
        broker,
        submission_intent_store=restarted_store,
    )

    tracked = gateway.execute_request(_request())

    assert tracked.lifecycle.status is OrderStatus.FILLED
    assert tracked.lifecycle.broker_order_id == "broker-99"
    assert broker.submit_calls == 1
    assert broker.get_calls == ["broker-99"]
    assert broker.find_calls == []


def test_gateway_fails_closed_when_durable_broker_binding_cannot_be_read(tmp_path: Path):
    store = _store(tmp_path)
    store.create(
        client_order_id="client-1",
        route="upstox",
        account_id="acct-1",
        symbol="NIFTY",
        side="BUY",
        quantity=1,
        request_fingerprint="fp-1",
    )
    store.record_broker_order("client-1", "missing-order", "NEW")

    class MissingBroker(RestartRecoveryBroker):
        def __init__(self):
            super().__init__()
            self.orders.clear()

    broker = MissingBroker()
    gateway = AuthoritativeLiveExecutionGateway(broker, submission_intent_store=_store(tmp_path))

    with pytest.raises(ExecutionSafetyError, match="submission outcome is unknown"):
        gateway.execute_request(_request())

    assert broker.submit_calls == 1
    assert broker.get_calls == ["missing-order"]
    assert broker.find_calls == []
