from datetime import date
from app.session_baseline import SessionBaselineStore


def test_baseline_is_initialized_once_per_session(tmp_path):
    store = SessionBaselineStore(str(tmp_path / "baseline.json"))
    first = store.get_or_initialize(date(2026, 8, 24), 100000)
    second = store.get_or_initialize(date(2026, 8, 24), 95000)
    assert first == second
    assert second.starting_equity == 100000


def test_new_session_creates_new_baseline(tmp_path):
    store = SessionBaselineStore(str(tmp_path / "baseline.json"))
    store.get_or_initialize(date(2026, 8, 24), 100000)
    next_day = store.get_or_initialize(date(2026, 8, 25), 98000)
    assert next_day.session_date == "2026-08-25"
    assert next_day.starting_equity == 98000


def test_restart_reads_persisted_baseline(tmp_path):
    path = str(tmp_path / "baseline.json")
    SessionBaselineStore(path).get_or_initialize(date(2026, 8, 24), 100000)
    restarted = SessionBaselineStore(path)
    assert restarted.load().starting_equity == 100000
