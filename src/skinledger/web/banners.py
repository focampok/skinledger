"""Demo banners for SIMULATED pages (P14)."""

from __future__ import annotations

import sqlite3

from skinledger import copy


def for_person(conn: sqlite3.Connection, person: sqlite3.Row) -> str | None:
    """The public sample gets its own banner; attached history gets the demo one."""
    if person["is_demo_public"]:
        return copy.SAMPLE_PROFILE_BANNER
    row = conn.execute(
        "SELECT 1 FROM captures WHERE person_id = ? AND data_label = 'SIMULATED' LIMIT 1",
        (int(person["id"]),),
    ).fetchone()
    if row is not None:
        return copy.VERDICT_SIMULATED_BANNER
    return None
