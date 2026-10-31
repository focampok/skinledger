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


def sample_products() -> list[dict[str, object]]:
    """The public sample's products, in the order they started."""
    conn = connect(db_path())
    try:
        rows = conn.execute(
            "SELECT pr.id, pr.name FROM products pr "
            "JOIN persons p ON p.id = pr.person_id "
            "WHERE p.is_demo_public = 1 ORDER BY pr.started_on, pr.id"
        ).fetchall()
        return [
            {"id": int(row["id"]), "name": row["name"]}
            for row in rows
        ]
    finally:
        conn.close()
