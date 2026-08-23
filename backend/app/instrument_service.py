from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Instrument


class InstrumentValidationError(ValueError):
    pass


class InstrumentService:
    """Canonical read/write service for tradable instruments."""

    VALID_ASSET_CLASSES = {"equity", "index", "future", "option", "currency", "commodity"}
    VALID_INSTRUMENT_TYPES = {"SPOT", "FUTURE", "OPTION"}
    VALID_OPTION_TYPES = {"CE", "PE"}

    def __init__(self, db: Session):
        self.db = db

    @classmethod
    def validate(cls, *, symbol: str, exchange: str, asset_class: str, instrument_type: str = "SPOT", underlying_symbol: str | None = None, expiry_date=None, strike_price: Decimal | None = None, option_type: str | None = None) -> None:
        if not symbol.strip() or not exchange.strip():
            raise InstrumentValidationError("symbol and exchange are required")
        if asset_class not in cls.VALID_ASSET_CLASSES:
            raise InstrumentValidationError("unsupported asset_class")
        if instrument_type not in cls.VALID_INSTRUMENT_TYPES:
            raise InstrumentValidationError("unsupported instrument_type")
        if instrument_type == "OPTION":
            if not underlying_symbol or expiry_date is None or strike_price is None or option_type not in cls.VALID_OPTION_TYPES:
                raise InstrumentValidationError("options require underlying_symbol, expiry_date, strike_price and CE/PE option_type")
            if strike_price <= 0:
                raise InstrumentValidationError("strike_price must be positive")
        elif any(value is not None for value in (strike_price, option_type)):
            raise InstrumentValidationError("strike_price and option_type are only valid for options")

    def upsert(self, **values) -> Instrument:
        self.validate(**values)
        symbol = values["symbol"].strip().upper()
        instrument = self.db.scalar(select(Instrument).where(Instrument.symbol == symbol))
        if instrument is None:
            instrument = Instrument(symbol=symbol, **{k: v for k, v in values.items() if k != "symbol"})
            self.db.add(instrument)
        else:
            for key, value in values.items():
                if key != "symbol":
                    setattr(instrument, key, value)
        self.db.flush()
        return instrument

    def get(self, symbol: str) -> Instrument | None:
        return self.db.scalar(select(Instrument).where(Instrument.symbol == symbol.strip().upper()))

    def list(self, *, exchange: str | None = None, asset_class: str | None = None) -> list[Instrument]:
        statement = select(Instrument).order_by(Instrument.symbol)
        if exchange:
            statement = statement.where(Instrument.exchange == exchange)
        if asset_class:
            statement = statement.where(Instrument.asset_class == asset_class)
        return list(self.db.scalars(statement).all())
