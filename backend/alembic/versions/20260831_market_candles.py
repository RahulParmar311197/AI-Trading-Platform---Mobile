from alembic import op
import sqlalchemy as sa

revision = "20260831_market_candles"
down_revision = "20260831_risk_reservation_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "market_candles" in inspector.get_table_names():
        return
    op.create_table(
        "market_candles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_market_candle_key"),
    )
    op.create_index("ix_market_candles_symbol", "market_candles", ["symbol"])
    op.create_index("ix_market_candles_timeframe", "market_candles", ["timeframe"])
    op.create_index("ix_market_candles_timestamp", "market_candles", ["timestamp"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "market_candles" not in inspector.get_table_names():
        return
    op.drop_table("market_candles")
