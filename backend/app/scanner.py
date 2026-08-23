from __future__ import annotations

from app.multi_timeframe import analyze


def scan(symbols: list[str], timeframes: list[str] | None = None, minimum_score: float = 1.5) -> list[dict]:
    results = []
    for symbol in symbols:
        result = analyze(symbol, timeframes)
        if abs(result["composite_score"]) >= minimum_score:
            results.append(result)
    return sorted(results, key=lambda item: abs(item["composite_score"]), reverse=True)
