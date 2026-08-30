import importlib.util

from sqlalchemy import create_engine, inspect, text


MIGRATION = "backend/alembic/versions/20260830_reconciliation_account_identity.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("reconciliation_account_identity_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_account_identity_migration_preserves_existing_values_on_sqlite(tmp_path):
    migration = _load_migration()
    engine = create_engine(f"sqlite:///{tmp_path / 'reconciliation.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE reconciliation_states ("
            "broker_account_id INTEGER NOT NULL, broker_route VARCHAR(160) NOT NULL, "
            "status VARCHAR(32) NOT NULL, trading_halted BOOLEAN NOT NULL, "
            "checked_at VARCHAR(64), order_drift_count INTEGER NOT NULL, "
            "position_drift_count INTEGER NOT NULL, updated_at DATETIME NOT NULL, "
            "PRIMARY KEY (broker_account_id, broker_route))"
        )
        connection.execute(text("INSERT INTO reconciliation_states VALUES (101, 'route-a', 'VERIFIED', 0, :checked, 0, 0, CURRENT_TIMESTAMP)"), {"checked": "2026-08-30T00:00:00+00:00"})

    with engine.begin() as connection:
        migration.op.get_bind = lambda: connection
        migration.upgrade()

    column = next(c for c in inspect(engine).get_columns("reconciliation_states") if c["name"] == "broker_account_id")
    assert "CHAR" in str(column["type"]).upper() or "TEXT" in str(column["type"]).upper() or "VARCHAR" in str(column["type"]).upper()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT broker_account_id FROM reconciliation_states")).scalar_one() == "101"
