from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.brokers.upstox_client import UpstoxAPIError, UpstoxClient


def test_list_data_rejects_object_instead_of_empty_list():
    with pytest.raises(UpstoxAPIError, match="positions.*invalid list data"):
        UpstoxClient._list_data({"data": {"unexpected": True}}, "positions")


def test_list_data_rejects_non_mapping_items():
    with pytest.raises(UpstoxAPIError, match="orders.*invalid list data"):
        UpstoxClient._list_data({"data": [{"order_id": "1"}, "bad"]}, "orders")


def test_object_data_rejects_list_instead_of_wrapping_it():
    with pytest.raises(UpstoxAPIError, match="profile.*invalid object data"):
        UpstoxClient._object_data({"data": []}, "profile")


def test_object_data_accepts_successful_mapping():
    assert UpstoxClient._object_data({"status": "success", "data": {"user_id": "UCC-42"}}, "profile") == {
        "user_id": "UCC-42"
    }


def test_list_data_accepts_successful_mapping_items():
    assert UpstoxClient._list_data({"status": "success", "data": [{"order_id": "1"}]}, "orders") == [
        {"order_id": "1"}
    ]


def test_missing_token_rejected():
    with pytest.raises(ValueError, match="access token"):
        UpstoxClient("")


def test_get_quote_uses_bearer_auth_and_encodes_parameter():
    client = UpstoxClient("secret")
    response = {"status": "success", "data": {"last_price": 100}}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(response).encode()

    with patch("app.brokers.upstox_client.urlopen", return_value=FakeResponse()) as open_url:
        result = client.get_quote("NSE_EQ|INE002A01018")

    assert result == {"last_price": 100}
    request = open_url.call_args.args[0]
    assert request.headers["Authorization"] == "Bearer secret"
    assert "instrument_key=NSE_EQ%7CINE002A01018" in request.full_url


def test_network_failure_is_normalized():
    client = UpstoxClient("secret")

    with patch("app.brokers.upstox_client.urlopen", side_effect=OSError("network failure")):
        with pytest.raises(UpstoxAPIError, match="network request failed"):
            client.get_profile()


def test_unsuccessful_payload_is_rejected():
    client = UpstoxClient("secret")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"status":"error","errors":[{"message":"bad request"}]}'

    with patch("app.brokers.upstox_client.urlopen", return_value=FakeResponse()):
        with pytest.raises(UpstoxAPIError, match="unsuccessful response"):
            client.get_profile()


def test_empty_quote_instrument_rejected():
    client = UpstoxClient("secret")
    with pytest.raises(ValueError, match="instrument_key"):
        client.get_quote("")
