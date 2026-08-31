from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from .models import Candle, Instrument, Tick, Timeframe
from .provider import HistoricalMarketDataProvider


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
        full = payload.get("fullFeed")
        if isinstance(full, Mapping):
            market_ff = full.get("marketFF")
            if isinstance(market_ff, Mapping) and isinstance(market_ff.get("ltpc"), Mapping):
                return market_ff["ltpc"]
        return None

    @staticmethod
    def _timestamp(value: Any) -> datetime:
        if value is None:
            raise ValueError("Upstox tick has no timestamp")
        milliseconds = int(value)
        return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)


class UpstoxHistoricalMarketDataProvider(HistoricalMarketDataProvider):
    """Bridge the account-scoped Upstox REST adapter into canonical candles.

    The broker adapter remains responsible for authentication and transport;
    this provider owns only conversion into the canonical ``Candle`` contract.
    """

    _TIMEFRAME_REQUESTS: dict[Timeframe, tuple[str, int]] = {
        Timeframe.ONE_MINUTE: ("minutes", 1),
        Timeframe.THREE_MINUTES: ("minutes", 3),
        Timeframe.FIVE_MINUTES: ("minutes", 5),
        Timeframe.FIFTEEN_MINUTES: ("minutes", 15),
        Timeframe.THIRTY_MINUTES: ("minutes", 30),
        Timeframe.ONE_HOUR: ("hours", 1),
        Timeframe.FOUR_HOURS: ("hours", 4),
        Timeframe.ONE_DAY: ("days", 1),
        Timeframe.ONE_WEEK: ("weeks", 1),
    }

    def __init__(self, adapter: Any):
        if not hasattr(adapter, "get_historical_candles"):
            raise TypeError("Upstox adapter must expose get_historical_candles")
        self._adapter = adapter

    async def candles(
        self,
        instrument: Instrument,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> Sequence[Candle]:
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("start must be timezone-aware")
        if end.tzinfo is None or end.utcoffset() is None:
            raise ValueError("end must be timezone-aware")
        if end < start:
            raise ValueError("end must be >= start")
        request = self._TIMEFRAME_REQUESTS.get(timeframe)
        if request is None:
            raise ValueError(f"unsupported Upstox timeframe: {timeframe}")
        instrument_key = instrument.instrument_token
        if not instrument_key:
            raise ValueError("Upstox historical candles require instrument.instrument_token")
        unit, interval = request
        rows = self._adapter.get_historical_candles(
            instrument_key=instrument_key,
            unit=unit,
            interval=interval,
            to_date=end.astimezone(timezone.utc).date().isoformat(),
            from_date=start.astimezone(timezone.utc).date().isoformat(),
        )
        candles: list[Candle] = []
        for row in rows:
            timestamp = self._timestamp(row.get("timestamp"))
            if timestamp < start.astimezone(timezone.utc) or timestamp > end.astimezone(timezone.utc):
                continue
            candles.append(
                Candle(
                    instrument=instrument,
                    timeframe=timeframe,
                    timestamp=timestamp,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume") or 0),
                )
            )
        candles.sort(key=lambda candle: candle.timestamp)
        deduped: dict[datetime, Candle] = {candle.timestamp: candle for candle in candles}
        return list(deduped.values())

    @staticmethod
    def _timestamp(value: Any) -> datetime:
        if value is None:
            raise ValueError("Upstox historical candle has no timestamp")
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Upstox historical candle timestamp must be timezone-aware")
            return value.astimezone(timezone.utc)
        text = str(value).strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid Upstox historical candle timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Upstox historical candle timestamp must be timezone-aware")
        return parsed.astimezone(timezone.utc)
