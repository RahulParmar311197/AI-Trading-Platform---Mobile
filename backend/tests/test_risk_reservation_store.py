from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.risk_reservation import RiskReservationRecord
from app.risk_reservation_store import RiskReservationStore


def _store(tmp_path: Path) -> RiskReservationStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'risk.sqlite'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine, tables=[RiskReservationRecord.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return RiskReservationStore(Session)


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
    store.reserve(
        reservation_id="r1", client_order_id="c1", broker_account_id="001",
        broker_route="upstox", amount=20, current_exposure=70, max_total_exposure=100,
    )
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
    store.reserve(
        reservation_id="r1", client_order_id="c1", broker_account_id="001",
        broker_route="upstox", amount=10, current_exposure=0, max_total_exposure=100,
    )
    with pytest.raises(RuntimeError, match="active risk reservation"):
        store.reserve(
            reservation_id="r2", client_order_id="c1", broker_account_id="001",
            broker_route="upstox", amount=10, current_exposure=0, max_total_exposure=100,
        )
