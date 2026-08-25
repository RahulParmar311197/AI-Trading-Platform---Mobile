from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.orders import _broker_route_for_account


def test_broker_route_matches_account_route_registry_contract():
    account = SimpleNamespace(id=42, broker="Upstox")

    assert _broker_route_for_account(account) == "upstox:account:42"


def test_broker_route_rejects_missing_identity():
    with pytest.raises(HTTPException) as exc:
        _broker_route_for_account(SimpleNamespace(id=None, broker="upstox"))

    assert exc.value.status_code == 409
    assert exc.value.detail == "BROKER_ACCOUNT_ROUTE_UNAVAILABLE"


def test_broker_route_rejects_blank_broker():
    with pytest.raises(HTTPException) as exc:
        _broker_route_for_account(SimpleNamespace(id=42, broker="   "))

    assert exc.value.status_code == 409
    assert exc.value.detail == "BROKER_ACCOUNT_ROUTE_UNAVAILABLE"
