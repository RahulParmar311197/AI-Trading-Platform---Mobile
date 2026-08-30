from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def run_startup_migrations() -> None:
    """Upgrade the application database to the Alembic head before trading startup."""
    alembic_ini = BACKEND_ROOT / "alembic.ini"
    alembic_dir = BACKEND_ROOT / "alembic"
    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(alembic_dir))
    command.upgrade(config, "head")
