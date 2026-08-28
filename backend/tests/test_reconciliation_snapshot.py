from app.reconciliation_snapshot import next_snapshot, snapshot_fingerprint


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


def test_observation_metadata_can_be_ignored_before_fingerprinting():
    base = {"symbol": "NIFTY", "quantity": 1}
    with_metadata_a = {**base, "observed_at": "2026-08-28T12:00:00Z"}
    with_metadata_b = {**base, "observed_at": "2026-08-28T12:01:00Z"}
    assert snapshot_fingerprint(positions=[base]) == snapshot_fingerprint(positions=[base])
    assert snapshot_fingerprint(positions=[with_metadata_a]) != snapshot_fingerprint(positions=[with_metadata_b])
