from __future__ import annotations

import json
from pathlib import Path

from app.symbol_registry import SymbolMetadata, SymbolRegistry


def load_symbol_registry(path: str | Path) -> SymbolRegistry:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"symbol catalog not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    symbols: list[SymbolMetadata] = []

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("symbol catalog entries must be objects")
            exchange = str(item.get("exchange", "NSE"))
            symbols.append(
                SymbolMetadata(
                    str(item["symbol"]),
                    exchange,
                    str(item.get("asset_class", "equity")),
                )
            )
    elif isinstance(data, dict):
        # Also support the exchange-keyed catalog used by the production config:
        # {"NSE": [{"symbol": "NIFTY", ...}], "BSE": [...]}
        for exchange, entries in data.items():
            if not isinstance(entries, list):
                raise ValueError(f"symbol catalog exchange {exchange} must contain an array")
            for item in entries:
                if not isinstance(item, dict) or "symbol" not in item:
                    raise ValueError("symbol catalog entries must contain symbol")
                symbols.append(
                    SymbolMetadata(
                        str(item["symbol"]),
                        str(exchange),
                        str(item.get("asset_class", "equity")),
                    )
                )
    else:
        raise ValueError("symbol catalog must be a JSON array or exchange mapping")

    return SymbolRegistry(symbols)
