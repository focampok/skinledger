"""SQLite access: WAL, per-request connections and idempotent migrations."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from skinledger.config import Settings, get_settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def db_path(settings: Settings | None = None) -> Path:
    """Path of the SQLite file inside DATA_DIR."""
    settings = settings if settings is not None else get_settings()
    return settings.data_dir / "skinledger.sqlite"


def connect(path: Path) -> sqlite3.Connection:
    """Open one connection with the pragmas the app relies on."""
    # FastAPI may resolve the dependency and run the endpoint on different threads.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(path: Path | None = None, settings: Settings | None = None) -> Path:
    """Create the schema when missing; safe to call on every startup."""
    target = path if path is not None else db_path(settings)
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = connect(target)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()
    return target


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: exactly one connection per request, closed afterwards."""
    conn = connect(db_path())
    try:
        yield conn
    finally:
        conn.close()
