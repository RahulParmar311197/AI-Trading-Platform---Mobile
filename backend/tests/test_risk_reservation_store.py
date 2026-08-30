from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.risk_reservation import RiskReservationRecord
from app.risk_reservation_store import RiskReservationStore


def _store(tmp_path: Path) -> RiskReservationStore:
    tmp_path.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{tmp_path / 'risk.sqlite'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine, tables=[RiskReservationRecord.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return RiskReservationStore(Session)


def _reserve(store: RiskReservationStore, reservation_id="r1", client_order_id="c1", amount=20):
    return store.reserve(
        reservation_id=reservation_id,
        client_order_id=client_order_id,
        broker_account_id="001",
        broker_route="upstox",
        amount=amount,
        current_exposure=70,
        max_total_exposure=100,
    )


def test_reservation_respects_combined_current_and_active_exposure(tmp_path: Path):
    store = _store(tmp_path)
    first = store.reserve(
        reservation_id="r1", client_order_id="c1", broker_account_id="001",
        broker_route="upstox", amount=10, current_exposure=70, max_total_exposure=100,
    )
    assert first == "r1"
    with pytest.raises(RuntimeError, match="concurrent exposure limit"):
        store.reserve(
            reservation_id="r2", client_order_id="c2", broker_account_id="001",
            broker_route="upstox", amount=21, current_exposure=70, max_total_exposure=100,
        )
    assert store.active_amount(broker_account_id="001", broker_route="upstox") == 10


def test_reservation_release_frees_capacity(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store)
    store.release("r1")
    assert store.active_amount(broker_account_id="001", broker_route="upstox") == 0
    store.reserve(
        reservation_id="r2", client_order_id="c2", broker_account_id="001",
        broker_route="upstox", amount=30, current_exposure=70, max_total_exposure=100,
    )


def test_opaque_account_ids_are_isolated(tmp_path: Path):
    store = _store(tmp_path)
    store.reserve(
        reservation_id="r1", client_order_id="c1", broker_account_id="001",
        broker_route="upstox", amount=25, current_exposure=70, max_total_exposure=100,
    )
    store.reserve(
        reservation_id="r2", client_order_id="c2", broker_account_id="1",
        broker_route="upstox", amount=25, current_exposure=70, max_total_exposure=100,
    )
    assert store.active_amount(broker_account_id="001", broker_route="upstox") == 25
    assert store.active_amount(broker_account_id="1", broker_route="upstox") == 25


def test_duplicate_active_client_order_is_rejected(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, reservation_id="r1", client_order_id="c1", amount=10)
    with pytest.raises(RuntimeError, match="active risk reservation"):
        store.reserve(
            reservation_id="r2", client_order_id="c1", broker_account_id="001",
            broker_route="upstox", amount=10, current_exposure=0, max_total_exposure=100,
        )


def test_filled_cancelled_or_rejected_releases_reservation(tmp_path: Path):
    for status in ("FILLED", "CANCELLED", "REJECTED"):
        store = _store(tmp_path / status.lower())
        _reserve(store)
        assert store.reconcile(reservation_id="r1", broker_status=status) == store.RELEASED
        assert store.active_amount(broker_account_id="001", broker_route="upstox") == 0
        assert store.reconcile(reservation_id="r1", broker_status=status) == store.RELEASED


def test_partial_fill_only_shrinks_reservation(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, amount=20)
    assert store.reconcile(reservation_id="r1", broker_status="PARTIALLY_FILLED", remaining_amount=7) == store.ACTIVE
    assert store.active_amount(broker_account_id="001", broker_route="upstox") == 7
    with pytest.raises(RuntimeError, match="cannot increase"):
        store.reconcile(reservation_id="r1", broker_status="PARTIALLY_FILLED", remaining_amount=8)
    assert store.active_amount(broker_account_id="001", broker_route="upstox") == 7


def test_partial_fill_zero_releases_and_unknown_state_keeps_reservation(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, amount=20)
    with pytest.raises(RuntimeError, match="cannot release"):
        store.reconcile(reservation_id="r1", broker_status="UNKNOWN")
    assert store.active_amount(broker_account_id="001", broker_route="upstox") == 20
    assert store.reconcile(reservation_id="r1", broker_status="PARTIALLY_FILLED", remaining_amount=0) == store.RELEASED
    assert store.active_amount(broker_account_id="001", broker_route="upstox") == 0


def test_client_order_binding_reconciles_idempotently(tmp_path: Path):
    store = _store(tmp_path)
    _reserve(store, reservation_id="r-client", client_order_id="client-42", amount=20)
    assert store.reconcile_client_order(client_order_id="client-42", broker_status="PARTIALLY_FILLED", remaining_amount=6) == store.ACTIVE
    assert store.active_amount(broker_account_id="001", broker_route="upstox") == 6
    assert store.reconcile_client_order(client_order_id="client-42", broker_status="FILLED") == store.RELEASED
    assert store.reconcile_client_order(client_order_id="client-42", broker_status="FILLED") == store.RELEASED
    assert store.reconcile_client_order(client_order_id="missing", broker_status="FILLED") is None
