from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.config import get_settings

MIGRATION_LOCK_ID = 6_821_904_521_001_207_143


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return config


def migrate_database() -> None:
    """Apply immutable migrations, serializing PostgreSQL deploys with an advisory lock."""
    settings = get_settings()
    migration_url = settings.migration_database_url
    if not migration_url or not migration_url.startswith("postgresql"):
        command.upgrade(_alembic_config(), "head")
        return
    lock_engine = create_engine(migration_url, pool_pre_ping=True)
    try:
        with lock_engine.connect() as connection:
            connection.execute(
                text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID}
            )
            try:
                command.upgrade(_alembic_config(), "head")
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": MIGRATION_LOCK_ID},
                )
    finally:
        lock_engine.dispose()


def exec_uvicorn() -> None:
    port = os.environ.get("PORT", "8000")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise RuntimeError("PORT must be an integer between 1 and 65535")
    os.execvp(
        "uvicorn",
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port],
    )
