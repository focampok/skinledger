"""Shared helpers for the public sample profile (/try and /demo)."""

from __future__ import annotations

from skinledger.db import connect, db_path


def sample_person_id() -> int | None:
    conn = connect(db_path())
    try:
        row = conn.execute(
            "SELECT id FROM persons WHERE is_demo_public = 1 ORDER BY id LIMIT 1"
        ).fetchone()
        return int(row["id"]) if row is not None else None
    finally:
        conn.close()
