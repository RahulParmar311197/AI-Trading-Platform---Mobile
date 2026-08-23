from __future__ import annotations

from dataclasses import dataclass
from math import erf, exp, log, pi, sqrt


@dataclass(frozen=True)
class Greeks:
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _pdf(x: float) -> float:
    return exp(-0.5 * x * x) / sqrt(2.0 * pi)


def black_scholes(spot: float, strike: float, time_years: float, rate: float, volatility: float, option: str) -> Greeks:
    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive")
    if time_years <= 0:
        raise ValueError("time_years must be positive")
    if volatility <= 0:
        raise ValueError("volatility must be positive")
    if option not in {"CALL", "PUT"}:
        raise ValueError("option must be CALL or PUT")

    sqrt_t = sqrt(time_years)
    d1 = (log(spot / strike) + (rate + 0.5 * volatility**2) * time_years) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    nd1 = _pdf(d1)
    discount = exp(-rate * time_years)

    if option == "CALL":
        price = spot * _cdf(d1) - strike * discount * _cdf(d2)
        delta = _cdf(d1)
        theta = -(spot * nd1 * volatility / (2 * sqrt_t)) - rate * strike * discount * _cdf(d2)
        rho = strike * time_years * discount * _cdf(d2)
    else:
        price = strike * discount * _cdf(-d2) - spot * _cdf(-d1)
        delta = _cdf(d1) - 1.0
        theta = -(spot * nd1 * volatility / (2 * sqrt_t)) + rate * strike * discount * _cdf(-d2)
        rho = -strike * time_years * discount * _cdf(-d2)

    gamma = nd1 / (spot * volatility * sqrt_t)
    vega = spot * nd1 * sqrt_t
    return Greeks(price, delta, gamma, theta, vega, rho)
