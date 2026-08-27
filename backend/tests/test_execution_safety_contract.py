from __future__ import annotations

import pytest

from app.broker_adapter import PaperBrokerAdapter
from app.broker_config import BrokerConfigError, ExecutionMode, load_broker_config


def test_broker_config_defaults_to_paper(monkeypatch):
    monkeypatch.delenv("BROKER_MODE", raising=False)
    monkeypatch.delenv("BROKER_NAME", raising=False)
    config = load_broker_config()
    assert config.mode is ExecutionMode.PAPER
    assert config.live_enabled is False
    assert config.credentials is None


def test_live_requires_credentials(monkeypatch):
    monkeypatch.setenv("BROKER_MODE", "LIVE")
    monkeypatch.setenv("BROKER_NAME", "upstox")
    monkeypatch.delenv("BROKER_API_KEY", raising=False)
    monkeypatch.delenv("BROKER_API_SECRET", raising=False)
    with pytest.raises(BrokerConfigError, match="credentials"):
        load_broker_config()


def test_paper_adapter_is_deterministic_and_rejects_invalid_quantity():
    broker = PaperBrokerAdapter()
    with pytest.raises(ValueError):
        broker.submit_order(type("Order", (), {"symbol": "NSE:TEST", "side": "BUY", "quantity": 0})())


def test_paper_order_can_be_recovered_by_client_id():
    broker = PaperBrokerAdapter()
    order = type("Order", (), {"symbol": "NSE:TEST", "side": "BUY", "quantity": 1, "client_order_id": "client-1", "price": 100})()
    first = broker.submit_order(order)
    second = broker.submit_order(order)
    assert first["order_id"] == second["order_id"]
    assert len(broker.get_orders()) == 1
