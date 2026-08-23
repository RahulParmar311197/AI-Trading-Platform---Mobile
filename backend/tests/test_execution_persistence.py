from pathlib import Path

import pytest

from app.order_lifecycle import OrderLifecycle, OrderStatus
from app.execution_persistence import ExecutionStateStore


def test_execution_state_round_trip(tmp_path):
    path = tmp_path / "execution.json"
    source = OrderLifecycle()
    source.create("o1", "NIFTY", "BUY", 10)
    source.transition("o1", OrderStatus.FILLED, 10, 100.0)
    store = ExecutionStateStore(str(path))
    store.save(source)

    restored = OrderLifecycle()
    assert store.load(restored)
    assert restored.orders["o1"].status == OrderStatus.FILLED
    assert restored.orders["o1"].filled_quantity == 10
    assert restored.orders["o1"].applied_fill_quantity == 10
    assert restored.orders["o1"].applied_fill_value == 1000
    assert restored.positions["NIFTY"].quantity == 10


def test_partial_fill_restart_does_not_double_count_reconciliation(tmp_path):
    path = tmp_path / "execution.json"
    source = OrderLifecycle()
    source.create("o1", "NIFTY", "BUY", 10)
    source.transition("o1", OrderStatus.PARTIALLY_FILLED, 4, 100.0)
    store = ExecutionStateStore(str(path))
    store.save(source)

    restored = OrderLifecycle()
    assert store.load(restored)
    restored.transition("o1", OrderStatus.FILLED, 10, 102.0)
    assert restored.orders["o1"].applied_fill_quantity == 10
    assert restored.positions["NIFTY"].quantity == 10

    store.save(restored)
    again = OrderLifecycle()
    assert store.load(again)
    again.transition("o1", OrderStatus.FILLED, 10, 102.0)
    assert again.positions["NIFTY"].quantity == 10


def test_save_replaces_existing_state_and_leaves_no_tmp(tmp_path):
    path = tmp_path / "execution.json"
    store = ExecutionStateStore(str(path))
    first = OrderLifecycle()
    first.create("o1", "NIFTY", "BUY", 1)
    first.transition("o1", OrderStatus.FILLED, 1, 100.0)
    store.save(first)
    second = OrderLifecycle()
    second.create("o2", "BANKNIFTY", "BUY", 2)
    second.transition("o2", OrderStatus.FILLED, 2, 200.0)
    store.save(second)

    restored = OrderLifecycle()
    assert store.load(restored)
    assert "o1" not in restored.orders
    assert restored.orders["o2"].filled_quantity == 2
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_failed_replace_preserves_previous_primary_state(tmp_path, monkeypatch):
    path = tmp_path / "execution.json"
    store = ExecutionStateStore(str(path))
    original = OrderLifecycle()
    original.create("o1", "NIFTY", "BUY", 1)
    original.transition("o1", OrderStatus.FILLED, 1, 100.0)
    store.save(original)
    before = path.read_text(encoding="utf-8")

    replacement = OrderLifecycle()
    replacement.create("o2", "BANKNIFTY", "BUY", 2)
    real_replace = Path.replace

    def fail_primary_replace(self, target):
        if self.name.endswith(".tmp") and target == path:
            raise OSError("simulated crash during state replace")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_primary_replace)
    with pytest.raises(OSError, match="simulated crash"):
        store.save(replacement)

    assert path.read_text(encoding="utf-8") == before
    assert store.backup_path.exists()


def test_corrupt_primary_recovers_from_backup(tmp_path):
    path = tmp_path / "execution.json"
    source = OrderLifecycle()
    source.create("o1", "NIFTY", "BUY", 10)
    source.transition("o1", OrderStatus.FILLED, 10, 100.0)
    store = ExecutionStateStore(str(path))
    store.save(source)
    source.transition("o1", OrderStatus.CANCELLED, 10, 100.0)
    store.save(source)
    path.write_text("{not valid json", encoding="utf-8")

    restored = OrderLifecycle()
    assert store.load(restored)
    assert restored.orders["o1"].status == OrderStatus.FILLED
    assert restored.positions["NIFTY"].quantity == 10
    assert path.read_text(encoding="utf-8") == store.backup_path.read_text(encoding="utf-8")


def test_corrupt_primary_and_backup_fail_closed(tmp_path):
    path = tmp_path / "execution.json"
    store = ExecutionStateStore(str(path))
    path.write_text("{broken", encoding="utf-8")
    store.backup_path.write_text("{also broken", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unreadable"):
        store.load(OrderLifecycle())


def test_missing_state_returns_false(tmp_path):
    assert not ExecutionStateStore(str(tmp_path / "missing.json")).load(OrderLifecycle())
