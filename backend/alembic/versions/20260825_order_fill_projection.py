from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260825_order_fill_projection"
down_revision = "20260825_order_execution_parameters"
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "orders" not in inspector.get_table_names():
        return
    if not _has_column(inspector, "orders", "filled_quantity"):
        op.add_column("orders", sa.Column("filled_quantity", sa.Numeric(20, 6), nullable=True, server_default="0"))
    if not _has_column(inspector, "orders", "average_fill_price"):
        op.add_column("orders", sa.Column("average_fill_price", sa.Numeric(20, 8), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "orders" not in inspector.get_table_names():
        return
    for name in ("average_fill_price", "filled_quantity"):
        if _has_column(inspector, "orders", name):
            op.drop_column("orders", name)
