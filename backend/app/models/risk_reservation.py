from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RiskReservationRecord(Base):
    """Durable pre-trade exposure reservation scoped to one broker account/route."""

    __tablename__ = "risk_reservations"

    reservation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    client_order_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    broker_account_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    broker_route: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
