from alembic import op
import sqlalchemy as sa

revision = "20260831_risk_reservation_integrity"
down_revision = "20260831_risk_reservations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "risk_reservations" not in inspector.get_table_names():
        return

    dialect = bind.dialect.name
    if dialect == "sqlite":
        # SQLite CHECK constraints are still useful, but adding them to an
        # existing table requires table rebuilds. Production uses PostgreSQL.
        return

    op.create_check_constraint(
        "ck_risk_reservations_amount_positive",
        "risk_reservations",
        sa.text("amount > 0"),
    )
    op.create_check_constraint(
        "ck_risk_reservations_status_valid",
        "risk_reservations",
        sa.text("status IN ('ACTIVE', 'RELEASED', 'PARTIALLY_FILLED', 'FILLED', 'CANCELLED', 'REJECTED')"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    op.drop_constraint("ck_risk_reservations_status_valid", "risk_reservations", type_="check")
    op.drop_constraint("ck_risk_reservations_amount_positive", "risk_reservations", type_="check")
