import pytest

from app.upstox_adapter import UpstoxConfig


def test_upstox_slicing_is_rejected_at_configuration_time():
    with pytest.raises(ValueError, match="UPSTOX_SLICE is unsupported"):
        UpstoxConfig(access_token="token", slice_orders=True)


def test_upstox_default_slicing_is_disabled():
    config = UpstoxConfig(access_token="token")
    assert config.slice_orders is False
