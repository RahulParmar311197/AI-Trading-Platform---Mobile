from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260830_submission_intent_recovery"
down_revision = "20260830_submission_intents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("submission_intents")}
    if "broker_order_id" not in columns:
        op.add_column("submission_intents", sa.Column("broker_order_id", sa.String(length=128), nullable=True))
    if "broker_status" not in columns:
        op.add_column("submission_intents", sa.Column("broker_status", sa.String(length=32), nullable=True))
    if "recovered_at" not in columns:
        op.add_column("submission_intents", sa.Column("recovered_at", sa.DateTime(timezone=True), nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes("submission_intents")}
    if "ix_submission_intents_broker_order_id" not in indexes:
        op.create_index("ix_submission_intents_broker_order_id", "submission_intents", ["broker_order_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "submission_intents" not in inspector.get_table_names():
        return
    indexes = {index["name"] for index in inspector.get_indexes("submission_intents")}
    if "ix_submission_intents_broker_order_id" in indexes:
        op.drop_index("ix_submission_intents_broker_order_id", table_name="submission_intents")
    columns = {column["name"] for column in inspector.get_columns("submission_intents")}
    for name in ("recovered_at", "broker_status", "broker_order_id"):
        if name in columns:
            op.drop_column("submission_intents", name)
