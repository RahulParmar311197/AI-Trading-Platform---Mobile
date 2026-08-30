from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260830_submission_intents"
down_revision = "20260830_reconciliation_account_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "submission_intents" in inspector.get_table_names():
        return
    op.create_table(
        "submission_intents",
        sa.Column("client_order_id", sa.String(length=128), nullable=False),
        sa.Column("route", sa.String(length=160), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("client_order_id"),
    )
    op.create_index("ix_submission_intents_route", "submission_intents", ["route"])
    op.create_index("ix_submission_intents_account_id", "submission_intents", ["account_id"])
    op.create_index("ix_submission_intents_resolved_at", "submission_intents", ["resolved_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "submission_intents" not in inspector.get_table_names():
        return
    for index_name in (
        "ix_submission_intents_resolved_at",
        "ix_submission_intents_account_id",
        "ix_submission_intents_route",
    ):
        indexes = {index["name"] for index in inspector.get_indexes("submission_intents")}
        if index_name in indexes:
            op.drop_index(index_name, table_name="submission_intents")
    op.drop_table("submission_intents")
