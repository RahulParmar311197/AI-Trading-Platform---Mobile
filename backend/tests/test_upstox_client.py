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
