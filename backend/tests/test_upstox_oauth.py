import pytest

from app.brokers.upstox_oauth import validate_token_response


def test_validate_token_response_accepts_active_upstox_identity():
    result = validate_token_response(
        {
            "access_token": "token-123",
            "broker": "UPSTOX",
            "user_id": "UCC-42",
            "is_active": True,
        }
    )
    assert result == {
        "access_token": "token-123",
        "broker": "UPSTOX",
        "broker_user_id": "UCC-42",
    }


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"access_token": "token", "broker": "DHAN", "user_id": "UCC", "is_active": True}, "broker identity"),
        ({"access_token": "token", "broker": "UPSTOX", "is_active": True}, "user identity"),
        ({"access_token": "token", "broker": "UPSTOX", "user_id": "UCC", "is_active": False}, "not active"),
        ({"broker": "UPSTOX", "user_id": "UCC", "is_active": True}, "access token"),
    ],
)
def test_validate_token_response_fails_closed_on_invalid_identity(payload, message):
    with pytest.raises(ValueError, match=message):
        validate_token_response(payload)


def test_validate_token_response_rejects_non_object():
    with pytest.raises(ValueError, match="must be an object"):
        validate_token_response([])
