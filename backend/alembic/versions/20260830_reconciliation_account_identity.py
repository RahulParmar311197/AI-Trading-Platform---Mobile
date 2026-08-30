from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260830_reconciliation_account_identity"
down_revision = "20260830_reconciliation_states"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "reconciliation_states" not in inspector.get_table_names():
        return
    columns = {column["name"]: column for column in inspector.get_columns("reconciliation_states")}
    account_column = columns.get("broker_account_id")
    if account_column is None:
        raise RuntimeError("reconciliation_states.broker_account_id is missing")
    if isinstance(account_column["type"], sa.String):
        return
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE reconciliation_states "
            "ALTER COLUMN broker_account_id TYPE VARCHAR(128) "
            "USING CAST(broker_account_id AS VARCHAR(128))"
        )
        return
    with op.batch_alter_table("reconciliation_states", recreate="always") as batch_op:
        batch_op.alter_column(
            "broker_account_id",
            existing_type=sa.Integer(),
            type_=sa.String(length=128),
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "reconciliation_states" not in inspector.get_table_names():
        return
    columns = {column["name"]: column for column in inspector.get_columns("reconciliation_states")}
    account_column = columns.get("broker_account_id")
    if account_column is None:
        return
    if isinstance(account_column["type"], sa.Integer):
        return
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE reconciliation_states "
            "ALTER COLUMN broker_account_id TYPE INTEGER "
            "USING CAST(broker_account_id AS INTEGER)"
        )
        return
    with op.batch_alter_table("reconciliation_states", recreate="always") as batch_op:
        batch_op.alter_column(
            "broker_account_id",
            existing_type=sa.String(length=128),
            type_=sa.Integer(),
            existing_nullable=False,
        )
