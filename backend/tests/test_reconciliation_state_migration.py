from pathlib import Path


def test_reconciliation_state_migration_is_after_oauth_head_and_creates_durable_scope():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20260830_reconciliation_states.py"
    source = path.read_text(encoding="utf-8")

    assert 'revision = "20260830_reconciliation_states"' in source
    assert 'down_revision = "20260828_broker_oauth_states"' in source
    assert '"reconciliation_states"' in source
    assert 'sa.PrimaryKeyConstraint("broker_account_id", "broker_route")' in source
    assert 'sa.Column("status", sa.String(length=32), nullable=False)' in source
    assert 'sa.Column("trading_halted", sa.Boolean(), nullable=False)' in source
    assert 'sa.Column("checked_at", sa.String(length=64), nullable=True)' in source
    assert 'sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)' in source


def test_reconciliation_state_migration_is_idempotent_and_downgrade_safe():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20260830_reconciliation_states.py"
    source = path.read_text(encoding="utf-8")

    assert 'if "reconciliation_states" in inspector.get_table_names()' in source
    assert 'if "reconciliation_states" not in inspector.get_table_names()' in source
    assert 'op.drop_table("reconciliation_states")' in source
