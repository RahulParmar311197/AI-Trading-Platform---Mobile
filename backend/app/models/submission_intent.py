from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SubmissionIntentRecord(Base):
    """Durable idempotency record for a broker submission whose outcome may be lost."""

    __tablename__ = "submission_intents"

    client_order_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    route: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    account_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
