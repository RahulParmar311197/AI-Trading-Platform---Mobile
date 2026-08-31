import pytest

from app.market_data import Instrument
from app.market_data.realtime_quality import StreamHealth, TickSequenceTracker

RELIANCE = Instrument(symbol="RELIANCE", exchange="NSE")
INFY = Instrument(symbol="INFY", exchange="NSE")


def test_first_sequence_is_healthy():
    result = TickSequenceTracker().observe(RELIANCE, 100)
    assert result.accepted is True
    assert result.health == StreamHealth.HEALTHY


def test_contiguous_sequence_is_accepted():
    tracker = TickSequenceTracker()
    tracker.observe(RELIANCE, 100)
    result = tracker.observe(RELIANCE, 101)
    assert result.accepted is True
    assert result.gap is False


def test_duplicate_is_rejected_without_resync():
    tracker = TickSequenceTracker()
    tracker.observe(RELIANCE, 100)
    result = tracker.observe(RELIANCE, 100)
    assert result.duplicate is True
    assert result.accepted is False
    assert result.health == StreamHealth.HEALTHY


def test_forward_gap_requires_resync():
    tracker = TickSequenceTracker()
    tracker.observe(RELIANCE, 100)
    result = tracker.observe(RELIANCE, 103)
    assert result.gap is True
    assert result.expected == 101
    assert result.received == 103
    assert result.health == StreamHealth.RESYNC_REQUIRED


def test_out_of_order_requires_resync():
    tracker = TickSequenceTracker()
    tracker.observe(RELIANCE, 100)
    tracker.observe(RELIANCE, 101)
    result = tracker.observe(RELIANCE, 99)
    assert result.gap is True
    assert result.health == StreamHealth.RESYNC_REQUIRED


def test_instruments_are_independent():
    tracker = TickSequenceTracker()
    tracker.observe(RELIANCE, 10)
    tracker.observe(INFY, 50)
    assert tracker.observe(RELIANCE, 11).accepted is True
    assert tracker.observe(INFY, 51).accepted is True


def test_resync_restores_healthy_state():
    tracker = TickSequenceTracker()
    tracker.observe(RELIANCE, 100)
    tracker.observe(RELIANCE, 103)
    tracker.mark_resynced(RELIANCE, 103)
    result = tracker.observe(RELIANCE, 104)
    assert result.accepted is True
    assert result.health == StreamHealth.HEALTHY


def test_negative_sequence_is_invalid():
    with pytest.raises(ValueError, match="non-negative"):
        TickSequenceTracker().observe(RELIANCE, -1)
