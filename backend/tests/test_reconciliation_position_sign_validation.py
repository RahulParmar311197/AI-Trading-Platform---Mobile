import pytest

from app.reconciliation_validation import validate_positions


def test_explicit_signed_quantity_must_agree_with_position_side() -> None:
    with pytest.raises(ValueError, match="signed quantity conflicts with side"):
        validate_positions(
            [{"symbol": "NSE_EQ|TEST", "signed_quantity": 10, "side": "SELL"}],
            source="broker",
        )


def test_matching_explicit_signed_quantity_and_side_is_accepted() -> None:
    positions = validate_positions(
        [{"symbol": "NSE_EQ|TEST", "signed_quantity": -10, "side": "SELL"}],
        source="broker",
    )
    assert positions[0]["signed_quantity"] == -10


def test_flat_position_still_requires_a_valid_side() -> None:
    with pytest.raises(ValueError, match="unknown position side"):
        validate_positions(
            [{"symbol": "NSE_EQ|TEST", "signed_quantity": 0, "side": "UNKNOWN"}],
            source="broker",
        )
