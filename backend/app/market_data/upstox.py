from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .models import Instrument, Tick


class UpstoxMarketDataNormalizer:
    """Normalize Upstox Market Data Feed V3 LTPC messages into canonical ticks.

    The Upstox V3 feed is protobuf-backed, but the SDK/sample layer can expose
    decoded message objects. This adapter intentionally accepts a mapping-like
    decoded payload so transport/SDK details stay outside the canonical model.
    """

    def __init__(self, instruments: Mapping[str, Instrument]):
        self._instruments = dict(instruments)

    def normalize(self, message: Mapping[str, Any]) -> list[Tick]:
        if message.get("type") not in (None, "live_feed"):
            return []
        feeds = message.get("feeds") or {}
        if not isinstance(feeds, Mapping):
            raise ValueError("Upstox feeds must be a mapping")

        ticks: list[Tick] = []
        for instrument_key, payload in feeds.items():
            instrument = self._instruments.get(str(instrument_key))
            if instrument is None:
                continue
            ltpc = self._extract_ltpc(payload)
            if ltpc is None:
                continue
            price = float(ltpc["ltp"])
            timestamp = self._timestamp(ltpc.get("ltt") or message.get("currentTs"))
            volume = float(ltpc.get("ltq") or 0)
            ticks.append(
                Tick(
                    instrument=instrument,
                    timestamp=timestamp,
                    price=price,
                    volume=volume,
                )
            )
        return ticks

    @staticmethod
    def _extract_ltpc(payload: Any) -> Mapping[str, Any] | None:
        if not isinstance(payload, Mapping):
            return None
        direct = payload.get("ltpc")
        if isinstance(direct, Mapping):
            return direct
        # Full V3 feeds nest LTPC under fullFeed.marketFF.
        full = payload.get("fullFeed")
        if isinstance(full, Mapping):
            market_ff = full.get("marketFF")
            if isinstance(market_ff, Mapping) and isinstance(market_ff.get("ltpc"), Mapping):
                return market_ff["ltpc"]
        # SDK wrappers may expose the same structure with attributes.
        return None

    @staticmethod
    def _timestamp(value: Any) -> datetime:
        if value is None:
            raise ValueError("Upstox tick has no timestamp")
        milliseconds = int(value)
        return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
