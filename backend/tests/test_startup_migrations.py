from unittest.mock import patch

import pytest

from app.startup_migrations import run_startup_migrations


def test_startup_migrations_upgrade_to_head():
    with patch("app.startup_migrations.command.upgrade") as upgrade:
        run_startup_migrations()

    upgrade.assert_called_once()
    config, revision = upgrade.call_args.args
    assert revision == "head"
    assert config.get_main_option("script_location").endswith("backend/alembic")


def test_startup_migrations_propagates_failure():
    with patch(
        "app.startup_migrations.command.upgrade",
        side_effect=RuntimeError("migration failed"),
    ):
        with pytest.raises(RuntimeError, match="migration failed"):
            run_startup_migrations()
