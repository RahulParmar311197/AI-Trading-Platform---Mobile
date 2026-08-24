import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_decision_execute_rejects_invalid_request():
    response = client.post('/api/decision/execute', json={})
    assert response.status_code in {400, 422}


def test_decision_execute_no_trade_never_reaches_execution():
    response = client.post('/api/decision/execute', json={
        'symbol': 'NIFTY',
        'decision': {'action': 'NO_TRADE', 'confidence': 0.10},
    })
    assert response.status_code in {200, 400, 422}
    if response.status_code == 200:
        body = response.json()
        assert body.get('executed') is False or body.get('status') in {'blocked', 'NO_TRADE'}


def test_decision_execute_rejects_side_mismatch():
    response = client.post('/api/decision/execute', json={
        'symbol': 'NIFTY',
        'decision': {'action': 'BUY', 'confidence': 0.90},
        'side': 'SELL',
        'quantity': 1,
    })
    assert response.status_code in {400, 403, 409, 422}
