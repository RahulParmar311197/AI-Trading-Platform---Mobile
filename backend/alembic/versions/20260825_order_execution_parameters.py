from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260825_order_execution_parameters"
down_revision = "20260823_instrument_fields"
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "orders" not in inspector.get_table_names():
        return
    additions = [
        ("price", sa.Numeric(20, 8)),
        ("stop", sa.Numeric(20, 8)),
        ("security_id", sa.String(128)),
    ]
    for name, column_type in additions:
        if not _has_column(inspector, "orders", name):
            op.add_column("orders", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "orders" not in inspector.get_table_names():
        return
    for name in ("security_id", "stop", "price"):
        if _has_column(inspector, "orders", name):
            op.drop_column("orders", name)
