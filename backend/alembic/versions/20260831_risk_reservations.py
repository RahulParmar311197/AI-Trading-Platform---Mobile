from alembic import op
import sqlalchemy as sa

revision = "20260831_risk_reservations"
down_revision = "20260830_submission_intent_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "risk_reservations" in inspector.get_table_names():
        return
    op.create_table(
        "risk_reservations",
        sa.Column("reservation_id", sa.String(length=128), nullable=False),
        sa.Column("client_order_id", sa.String(length=128), nullable=False),
        sa.Column("broker_account_id", sa.String(length=128), nullable=False),
        sa.Column("broker_route", sa.String(length=160), nullable=False),
        sa.Column("amount", sa.Numeric(24, 8), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("reservation_id"),
        sa.UniqueConstraint("client_order_id"),
    )
    op.create_index("ix_risk_reservations_client_order_id", "risk_reservations", ["client_order_id"], unique=True)
    op.create_index("ix_risk_reservations_broker_account_id", "risk_reservations", ["broker_account_id"])
    op.create_index("ix_risk_reservations_broker_route", "risk_reservations", ["broker_route"])
    op.create_index("ix_risk_reservations_status", "risk_reservations", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "risk_reservations" not in inspector.get_table_names():
        return
    op.drop_table("risk_reservations")
