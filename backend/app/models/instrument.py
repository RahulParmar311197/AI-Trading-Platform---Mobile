from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    asset_class: Mapped[str] = mapped_column(String(32), default="equity", index=True)
    instrument_type: Mapped[str] = mapped_column(String(32), default="SPOT", index=True)
    underlying_symbol: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    strike_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    option_type: Mapped[str | None] = mapped_column(String(4), nullable=True)
    tick_size: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    lot_size: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
