from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260825_broker_account_binding"
down_revision = "20260825_order_fill_projection"
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind(); inspector = sa.inspect(bind)
    if "orders" not in inspector.get_table_names(): return
    if not _has_column(inspector, "orders", "broker_account_id"):
        op.add_column("orders", sa.Column("broker_account_id", sa.Integer(), nullable=True))
        op.create_index("ix_orders_broker_account_id", "orders", ["broker_account_id"])
    if not _has_column(inspector, "orders", "broker_route"):
        op.add_column("orders", sa.Column("broker_route", sa.String(length=64), nullable=True))


def downgrade() -> None:
    bind = op.get_bind(); inspector = sa.inspect(bind)
    if "orders" not in inspector.get_table_names(): return
    if _has_column(inspector, "orders", "broker_route"): op.drop_column("orders", "broker_route")
    if _has_column(inspector, "orders", "broker_account_id"):
        op.drop_index("ix_orders_broker_account_id", table_name="orders")
        op.drop_column("orders", "broker_account_id")
