import pytest

from app.options_greeks import black_scholes


def test_atm_call_has_expected_basic_greeks():
    g = black_scholes(100, 100, 1, 0.05, 0.20, "CALL")
    assert 10.0 < g.price < 11.0
    assert 0.60 < g.delta < 0.65
    assert g.gamma > 0
    assert g.vega > 0
    assert g.rho > 0


def test_put_call_delta_relationship():
    call = black_scholes(100, 100, 1, 0.05, 0.20, "CALL")
    put = black_scholes(100, 100, 1, 0.05, 0.20, "PUT")
    assert abs((call.delta - put.delta) - 1.0) < 1e-10


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        black_scholes(0, 100, 1, 0.05, 0.2, "CALL")
    with pytest.raises(ValueError):
        black_scholes(100, 100, 0, 0.05, 0.2, "CALL")
    with pytest.raises(ValueError):
        black_scholes(100, 100, 1, 0.05, 0, "CALL")
    with pytest.raises(ValueError):
        black_scholes(100, 100, 1, 0.05, 0.2, "XYZ")
