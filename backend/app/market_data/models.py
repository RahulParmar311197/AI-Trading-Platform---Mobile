from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Timeframe(str, Enum):
    ONE_MINUTE = "1m"
    THREE_MINUTES = "3m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"


class Instrument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(min_length=1, max_length=100)
    exchange: str = Field(min_length=1, max_length=32)
    instrument_token: str | None = Field(default=None, max_length=128)

    @field_validator("symbol", "exchange")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("identifier cannot be empty")
        return value


class Tick(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    instrument: Instrument
    timestamp: datetime
    price: float = Field(gt=0)
    volume: float = Field(default=0, ge=0)

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    instrument: Instrument
    timeframe: Timeframe
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(default=0, ge=0)

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("high")
    @classmethod
    def validate_high(cls, value: float, info):
        low = info.data.get("low")
        opening = info.data.get("open")
        closing = info.data.get("close")
        if low is not None and value < low:
            raise ValueError("high must be >= low")
        if opening is not None and value < opening:
            raise ValueError("high must be >= open")
        if closing is not None and value < closing:
            raise ValueError("high must be >= close")
        return value

    @field_validator("low")
    @classmethod
    def validate_low(cls, value: float, info):
        opening = info.data.get("open")
        closing = info.data.get("close")
        high = info.data.get("high")
        if high is not None and value > high:
            raise ValueError("low must be <= high")
        if opening is not None and value > opening:
            raise ValueError("low must be <= open")
        if closing is not None and value > closing:
            raise ValueError("low must be <= close")
        return value
