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
    return 0.5 * (1 + erf(x / sqrt(2)))


def _pdf(x: float) -> float:
    return exp(-0.5 * x * x) / sqrt(2 * pi)


def black_scholes(spot: float, strike: float, time_years: float, rate: float, volatility: float, option: str = "CE") -> Greeks:
    if min(spot, strike, time_years, volatility) <= 0:
        raise ValueError("spot, strike, time and volatility must be positive")
    if option not in {"CE", "PE"}:
        raise ValueError("option must be CE or PE")
    sigma_sqrt_t = volatility * sqrt(time_years)
    d1 = (log(spot / strike) + (rate + 0.5 * volatility ** 2) * time_years) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t
    discount = exp(-rate * time_years)
    if option == "CE":
        price = spot * _cdf(d1) - strike * discount * _cdf(d2)
        delta = _cdf(d1)
        rho = strike * time_years * discount * _cdf(d2) / 100
    else:
        price = strike * discount * _cdf(-d2) - spot * _cdf(-d1)
        delta = _cdf(d1) - 1
        rho = -strike * time_years * discount * _cdf(-d2) / 100
    gamma = _pdf(d1) / (spot * sigma_sqrt_t)
    vega = spot * _pdf(d1) * sqrt(time_years) / 100
    theta = (-(spot * _pdf(d1) * volatility) / (2 * sqrt(time_years)) - rate * strike * discount * (_cdf(d2) if option == "CE" else _cdf(-d2))) / 365
    return Greeks(price, delta, gamma, theta, vega, rho)


def intrinsic_value(spot: float, strike: float, option: str) -> float:
    if option == "CE":
        return max(spot - strike, 0)
    if option == "PE":
        return max(strike - spot, 0)
    raise ValueError("option must be CE or PE")


def payoff(spot_at_expiry: float, strike: float, premium: float, quantity: float, option: str, side: str = "BUY") -> float:
    intrinsic = intrinsic_value(spot_at_expiry, strike, option)
    multiplier = 1 if side == "BUY" else -1
    return (intrinsic - premium) * quantity * multiplier
