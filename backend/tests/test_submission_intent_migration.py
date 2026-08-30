import importlib.util

from sqlalchemy import create_engine, inspect, text


MIGRATION = "backend/alembic/versions/20260830_submission_intents.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("submission_intents_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_submission_intent_migration_creates_unique_durable_schema(tmp_path):
    migration = _load_migration()
    engine = create_engine(f"sqlite:///{tmp_path / 'submission-intents.db'}")

    with engine.begin() as connection:
        migration.op.get_bind = lambda: connection
        migration.upgrade()

    inspector = inspect(engine)
    assert "submission_intents" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("submission_intents")}
    assert columns == {
        "client_order_id",
        "route",
        "account_id",
        "symbol",
        "side",
        "quantity",
        "request_fingerprint",
        "created_at",
        "resolved_at",
    }
    primary_key = inspector.get_pk_constraint("submission_intents")["constrained_columns"]
    assert primary_key == ["client_order_id"]

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO submission_intents "
                "(client_order_id, route, account_id, symbol, side, quantity, request_fingerprint, created_at) "
                "VALUES (:id, :route, :account, :symbol, :side, :quantity, :fp, CURRENT_TIMESTAMP)"
            ),
            {
                "id": "cli-1",
                "route": "upstox",
                "account": "001",
                "symbol": "NIFTY",
                "side": "BUY",
                "quantity": 1,
                "fp": "fp-1",
            },
        )
        try:
            connection.execute(
                text(
                    "INSERT INTO submission_intents "
                    "(client_order_id, route, account_id, symbol, side, quantity, request_fingerprint, created_at) "
                    "VALUES (:id, :route, :account, :symbol, :side, :quantity, :fp, CURRENT_TIMESTAMP)"
                ),
                {
                    "id": "cli-1",
                    "route": "upstox",
                    "account": "1",
                    "symbol": "NIFTY",
                    "side": "BUY",
                    "quantity": 1,
                    "fp": "fp-2",
                },
            )
        except Exception:
            pass
        else:
            raise AssertionError("duplicate client_order_id must be rejected")
