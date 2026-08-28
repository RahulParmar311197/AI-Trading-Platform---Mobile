from app.reconciliation_snapshot import ReconciliationSnapshot, next_snapshot, snapshot_fingerprint


def test_same_state_has_same_fingerprint():
    positions = [{"symbol": "NIFTY", "quantity": 2}, {"symbol": "BANKNIFTY", "quantity": -1}]
    assert snapshot_fingerprint(positions=positions) == snapshot_fingerprint(positions=list(reversed(positions)))


def test_quantity_change_changes_fingerprint():
    assert snapshot_fingerprint(positions=[{"symbol": "NIFTY", "quantity": 2}]) != snapshot_fingerprint(positions=[{"symbol": "NIFTY", "quantity": 3}])


def test_order_status_change_changes_fingerprint():
    a = [{"order_id": "1", "status": "OPEN"}]
    b = [{"order_id": "1", "status": "FILLED"}]
    assert snapshot_fingerprint(positions=[], orders=a) != snapshot_fingerprint(positions=[], orders=b)


def test_generation_changes_only_on_fingerprint_change():
    first = next_snapshot(None, positions=[{"symbol": "NIFTY", "quantity": 1}])
    same = next_snapshot(first, positions=[{"symbol": "NIFTY", "quantity": 1}])
    changed = next_snapshot(same, positions=[{"symbol": "NIFTY", "quantity": 2}])
    assert first.generation == 1
    assert same.generation == 1
    assert changed.generation == 2


def test_timestamp_is_not_part_of_fingerprint():
    assert snapshot_fingerprint(positions=[{"symbol": "NIFTY", "quantity": 1, "observed_at": "a"}]) != snapshot_fingerprint(positions=[{"symbol": "NIFTY", "quantity": 1, "observed_at": "b"}])
