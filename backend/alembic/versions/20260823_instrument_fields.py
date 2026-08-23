from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260823_instrument_fields"
down_revision = None
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "instruments" not in inspector.get_table_names():
        return
    additions = [
        ("instrument_type", sa.String(32), "SPOT"),
        ("underlying_symbol", sa.String(64), None),
        ("expiry_date", sa.DateTime(timezone=True), None),
        ("strike_price", sa.Numeric(20, 6), None),
        ("option_type", sa.String(4), None),
        ("tick_size", sa.Numeric(20, 8), None),
        ("lot_size", sa.Numeric(20, 6), None),
    ]
    for name, column_type, default in additions:
        if not _has_column(inspector, "instruments", name):
            op.add_column("instruments", sa.Column(name, column_type, nullable=True, server_default=default))
    inspector = sa.inspect(bind)
    for name in ("instrument_type", "underlying_symbol", "expiry_date"):
        op.create_index(f"ix_instruments_{name}", "instruments", [name], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "instruments" not in inspector.get_table_names():
        return
    for name in ("instrument_type", "underlying_symbol", "expiry_date"):
        indexes = {i["name"] for i in inspector.get_indexes("instruments")}
        if f"ix_instruments_{name}" in indexes:
            op.drop_index(f"ix_instruments_{name}", table_name="instruments")
    for name in ("lot_size", "tick_size", "option_type", "strike_price", "expiry_date", "underlying_symbol", "instrument_type"):
        if _has_column(inspector, "instruments", name):
            op.drop_column("instruments", name)
