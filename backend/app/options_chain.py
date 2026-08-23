from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from app.options_greeks import black_scholes


@dataclass(frozen=True)
class OptionQuote:
    strike: float
    option: str
    bid: float
    ask: float
    last: float
    open_interest: int = 0
    volume: int = 0
    implied_volatility: float | None = None

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2 if self.ask >= self.bid else self.last


def implied_volatility(spot: float, strike: float, time_years: float, rate: float, option: str, market_price: float, *, low: float = 1e-6, high: float = 5.0, tolerance: float = 1e-8, max_iterations: int = 100) -> float:
    if market_price <= 0 or not isfinite(market_price):
        raise ValueError("market_price must be positive and finite")
    if low <= 0 or high <= low or tolerance <= 0 or max_iterations < 1:
        raise ValueError("invalid IV solver bounds")
    low_price = black_scholes(spot, strike, time_years, rate, low, option).price
    high_price = black_scholes(spot, strike, time_years, rate, high, option).price
    if market_price < low_price or market_price > high_price:
        raise ValueError("market price is outside the supported volatility range")
    lo, hi = low, high
    for _ in range(max_iterations):
        mid = (lo + hi) / 2
        price = black_scholes(spot, strike, time_years, rate, mid, option).price
        if abs(price - market_price) <= tolerance:
            return mid
        if price < market_price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def enrich_chain(quotes: list[OptionQuote], spot: float, time_years: float, rate: float) -> list[OptionQuote]:
    if spot <= 0 or time_years <= 0:
        raise ValueError("spot and time_years must be positive")
    enriched: list[OptionQuote] = []
    for quote in quotes:
        if quote.strike <= 0 or quote.bid < 0 or quote.ask < 0:
            raise ValueError("invalid option quote")
        price = quote.mid
        iv = implied_volatility(spot, quote.strike, time_years, rate, quote.option, price) if price > 0 else None
        enriched.append(OptionQuote(quote.strike, quote.option.upper(), quote.bid, quote.ask, quote.last, quote.open_interest, quote.volume, iv))
    return sorted(enriched, key=lambda q: (q.strike, q.option))


def chain_summary(quotes: list[OptionQuote]) -> dict:
    calls = [q for q in quotes if q.option.upper() == "CALL"]
    puts = [q for q in quotes if q.option.upper() == "PUT"]
    call_oi = sum(q.open_interest for q in calls)
    put_oi = sum(q.open_interest for q in puts)
    call_volume = sum(q.volume for q in calls)
    put_volume = sum(q.volume for q in puts)
    return {
        "call_open_interest": call_oi,
        "put_open_interest": put_oi,
        "put_call_oi_ratio": put_oi / call_oi if call_oi else None,
        "call_volume": call_volume,
        "put_volume": put_volume,
        "put_call_volume_ratio": put_volume / call_volume if call_volume else None,
    }
