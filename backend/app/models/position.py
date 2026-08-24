from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=0)
    average_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=0)
    side: Mapped[str] = mapped_column(String(8), default="LONG")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
