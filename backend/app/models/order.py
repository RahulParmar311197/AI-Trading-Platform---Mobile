from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(index=True)
    broker_account_id: Mapped[int | None] = mapped_column(index=True, nullable=True)
    broker_route: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    side: Mapped[str] = mapped_column(String(8))
    order_type: Mapped[str] = mapped_column(String(16), default="MARKET")
    quantity: Mapped[float] = mapped_column(Numeric(20, 6))
    price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    stop: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    security_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    filled_quantity: Mapped[float] = mapped_column(Numeric(20, 6), default=0, nullable=False)
    average_fill_price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    broker_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
