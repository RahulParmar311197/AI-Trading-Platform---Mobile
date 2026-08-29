from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260830_reconciliation_states"
down_revision = "20260828_broker_oauth_states"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "reconciliation_states" in inspector.get_table_names():
        return
    op.create_table(
        "reconciliation_states",
        sa.Column("broker_account_id", sa.Integer(), nullable=False),
        sa.Column("broker_route", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trading_halted", sa.Boolean(), nullable=False),
        sa.Column("checked_at", sa.String(length=64), nullable=True),
        sa.Column("order_drift_count", sa.Integer(), nullable=False),
        sa.Column("position_drift_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("broker_account_id", "broker_route"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "reconciliation_states" not in inspector.get_table_names():
        return
    op.drop_table("reconciliation_states")
