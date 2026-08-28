from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.broker_account import BrokerAccount


class BrokerAccountService:
    """User-scoped persistence boundary for broker accounts."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, *, user_id: int, broker: str, account_label: str) -> BrokerAccount | None:
        return self.db.scalar(
            select(BrokerAccount).where(
                BrokerAccount.user_id == user_id,
                BrokerAccount.broker == broker,
                BrokerAccount.account_label == account_label,
            )
        )

    def upsert(
        self,
        *,
        user_id: int,
        broker: str,
        account_label: str,
        encrypted_credentials: str,
        status: str = "active",
    ) -> BrokerAccount:
        if not encrypted_credentials:
            raise ValueError("encrypted_credentials is required")
        if not broker or not account_label:
            raise ValueError("broker and account_label are required")

        account = self.get(
            user_id=user_id,
            broker=broker,
            account_label=account_label,
        )
        if account is None:
            account = BrokerAccount(
                user_id=user_id,
                broker=broker,
                account_label=account_label,
                encrypted_credentials=encrypted_credentials,
                status=status,
            )
            self.db.add(account)
        else:
            account.encrypted_credentials = encrypted_credentials
            account.status = status

        self.db.flush()
        return account

    def list_for_user(self, *, user_id: int) -> list[BrokerAccount]:
        return list(
            self.db.scalars(
                select(BrokerAccount)
                .where(BrokerAccount.user_id == user_id)
                .order_by(BrokerAccount.id)
            ).all()
        )
