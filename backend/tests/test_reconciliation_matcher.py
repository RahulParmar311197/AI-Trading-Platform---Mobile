from datetime import datetime, timedelta, timezone

from app.reconciliation_matcher import BrokerOrderSnapshot, InternalOrderCandidate, ReconciliationMatcher


def test_prefers_client_order_id():
    now = datetime.now(timezone.utc)
    candidate = InternalOrderCandidate("client-1", "NIFTY", "BUY", 5, now)
    broker = BrokerOrderSnapshot("broker-1", "NIFTY", "BUY", 5, now, client_order_id="client-1")
    result = ReconciliationMatcher.match(broker, [candidate])
    assert result is not None
    assert result.method == "CLIENT_ORDER_ID"


def test_strict_attribute_match():
    now = datetime.now(timezone.utc)
    candidate = InternalOrderCandidate("client-1", "NIFTY", "BUY", 5, now)
    broker = BrokerOrderSnapshot("broker-1", "NIFTY", "BUY", 5, now + timedelta(seconds=30))
    result = ReconciliationMatcher.match(broker, [candidate])
    assert result is not None
    assert result.method == "STRICT_ATTRIBUTES"


def test_ambiguous_candidates_fail_closed():
    now = datetime.now(timezone.utc)
    candidates = [
        InternalOrderCandidate("client-1", "NIFTY", "BUY", 5, now),
        InternalOrderCandidate("client-2", "NIFTY", "BUY", 5, now),
    ]
    broker = BrokerOrderSnapshot("broker-1", "NIFTY", "BUY", 5, now)
    assert ReconciliationMatcher.match(broker, candidates) is None


def test_old_candidate_is_not_matched():
    now = datetime.now(timezone.utc)
    candidate = InternalOrderCandidate("client-1", "NIFTY", "BUY", 5, now - timedelta(minutes=10))
    broker = BrokerOrderSnapshot("broker-1", "NIFTY", "BUY", 5, now)
    assert ReconciliationMatcher.match(broker, [candidate]) is None
