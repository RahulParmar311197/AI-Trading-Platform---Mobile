from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.risk_reservation import RiskReservationRecord
from app.risk_reservation_store import RiskReservationStore


def _store(tmp_path: Path) -> RiskReservationStore:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'risk.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine, tables=[RiskReservationRecord.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return RiskReservationStore(Session)


def _reserve(store: RiskReservationStore, client_order_id: str = "client-1", amount: float = 20) -> None:
    store.reserve(
        reservation_id=f"reservation-{client_order_id}",
        client_order_id=client_order_id,
        broker_account_id="001",
        broker_route="upstox:account:1",
        amount=amount,
        current_exposure=50,
        max_total_exposure=100,
    )


def test_authoritative_terminal_snapshot_releases_matching_reservation(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store)

    failures = store.reconcile_authoritative_orders(
        broker_orders=[
            {
                "client_order_id": "client-1",
                "order_id": "broker-1",
                "status": "FILLED",
                "quantity": 20,
                "filled_quantity": 20,
            }
        ],
        broker_account_id="001",
        broker_route="upstox:account:1",
    )

    assert failures == []
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 0


def test_authoritative_snapshot_missing_client_order_fails_closed_without_mutation(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store)

    failures = store.reconcile_authoritative_orders(
        broker_orders=[
            {
                "order_id": "broker-other",
                "status": "CANCELLED",
                "quantity": 20,
                "filled_quantity": 0,
            }
        ],
        broker_account_id="001",
        broker_route="upstox:account:1",
    )

    assert failures == [
        {"id": "client-1", "reason": "RISK_RESERVATION_BROKER_MATCH_MISSING"}
    ]
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 20


def test_authoritative_snapshot_partial_fill_requires_complete_fill_facts(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, amount=20)

    failures = store.reconcile_authoritative_orders(
        broker_orders=[
            {
                "client_order_id": "client-1",
                "order_id": "broker-1",
                "status": "PARTIALLY_FILLED",
                "quantity": 20,
            }
        ],
        broker_account_id="001",
        broker_route="upstox:account:1",
    )

    assert failures == [
        {"id": "client-1", "reason": "RISK_RESERVATION_PARTIAL_FILL_FACTS_MISSING"}
    ]
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 20


def test_authoritative_snapshot_partial_fill_only_shrinks_reservation(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, amount=20)

    failures = store.reconcile_authoritative_orders(
        broker_orders=[
            {
                "client_order_id": "client-1",
                "order_id": "broker-1",
                "status": "PARTIALLY_FILLED",
                "quantity": 20,
                "filled_quantity": 13,
            }
        ],
        broker_account_id="001",
        broker_route="upstox:account:1",
    )

    assert failures == []
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 7


def test_authoritative_snapshot_does_not_mutate_when_any_reservation_is_ambiguous(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, client_order_id="client-1", amount=20)
    _reserve(store, client_order_id="client-2", amount=10)

    failures = store.reconcile_authoritative_orders(
        broker_orders=[
            {
                "client_order_id": "client-1",
                "order_id": "broker-1",
                "status": "CANCELLED",
                "quantity": 20,
                "filled_quantity": 0,
            }
        ],
        broker_account_id="001",
        broker_route="upstox:account:1",
    )

    assert failures == [
        {"id": "client-2", "reason": "RISK_RESERVATION_BROKER_MATCH_MISSING"}
    ]
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 30


def test_authoritative_snapshot_rejects_orphan_active_broker_order(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, client_order_id="client-1", amount=20)

    failures = store.reconcile_authoritative_orders(
        broker_orders=[
            {
                "client_order_id": "client-1",
                "order_id": "broker-1",
                "status": "OPEN",
                "quantity": 20,
                "filled_quantity": 0,
            },
            {
                "client_order_id": "orphan-client",
                "order_id": "broker-orphan",
                "status": "OPEN",
                "quantity": 5,
                "filled_quantity": 0,
            },
        ],
        broker_account_id="001",
        broker_route="upstox:account:1",
    )

    assert failures == [
        {"id": "orphan-client", "reason": "RISK_RESERVATION_ORPHAN_BROKER_ORDER"}
    ]
    assert store.active_amount(broker_account_id="001", broker_route="upstox:account:1") == 20
