from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260828_broker_oauth_states"
down_revision = "20260825_order_fill_projection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "broker_oauth_states" in inspector.get_table_names():
        return
    op.create_table(
        "broker_oauth_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("broker", sa.String(length=40), nullable=False),
        sa.Column("account_label", sa.String(length=80), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("state_hash"),
    )
    op.create_index("ix_broker_oauth_states_user_id", "broker_oauth_states", ["user_id"])
    op.create_index("ix_broker_oauth_states_state_hash", "broker_oauth_states", ["state_hash"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "broker_oauth_states" not in inspector.get_table_names():
        return
    op.drop_index("ix_broker_oauth_states_state_hash", table_name="broker_oauth_states")
    op.drop_index("ix_broker_oauth_states_user_id", table_name="broker_oauth_states")
    op.drop_table("broker_oauth_states")
