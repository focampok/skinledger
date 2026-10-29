"""Persistence and I/O for the pure verdict engine (P10).

verdict.py stays pure; this thin module loads the person's captures and bands,
calls compute_verdict, writes the verdicts row with payload_json and logs one
verdict.computed event (product_id, outcome and flags only).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, date, datetime

from skinledger import logs, noise, usage
from skinledger import verdict as engine

PERSISTED_OUTCOMES = frozenset(
    {engine.KEEP, engine.NO_CHANGE, engine.WORSE, engine.TOO_EARLY, engine.NO_BAND}
)


def _captured_on(value: object) -> str | None:
    """The America/Guatemala calendar day of a stored UTC timestamp."""
    text = str(value or "")
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text[:10] or None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return usage.guatemala_day(moment).isoformat()


def _load_captures(
    conn: sqlite3.Connection, person_id: int
) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT id, captured_at, data_label, source, status, is_baseline_pair "
        "FROM captures WHERE person_id = ? AND status = 'success' "
        "ORDER BY captured_at, id",
        (person_id,),
    ).fetchall()
    capture_ids = [int(row["id"]) for row in rows]
    scores: dict[int, dict[str, float]] = {}
    masks: dict[int, dict[str, str]] = {}
    if capture_ids:
        placeholders = ", ".join("?" for _ in capture_ids)
        for row in conn.execute(
            "SELECT capture_id, aspect, raw_score FROM aspect_scores "
            f"WHERE capture_id IN ({placeholders})",
            tuple(capture_ids),
        ):
            if row["raw_score"] is not None:
                scores.setdefault(int(row["capture_id"]), {})[row["aspect"]] = float(
                    row["raw_score"]
                )
        for row in conn.execute(
            "SELECT capture_id, aspect, file_path FROM masks "
            f"WHERE capture_id IN ({placeholders})",
            tuple(capture_ids),
        ):
            masks.setdefault(int(row["capture_id"]), {})[row["aspect"]] = row[
                "file_path"
            ]
    return [
        {
            "id": int(row["id"]),
            "captured_at": row["captured_at"],
            "captured_on": _captured_on(row["captured_at"]),
            "data_label": row["data_label"],
            "source": row["source"],
            "status": row["status"],
            "is_baseline_pair": bool(row["is_baseline_pair"]),
            "scores": scores.get(int(row["id"]), {}),
            "masks": masks.get(int(row["id"]), {}),
        }
        for row in rows
    ]


def _flags(computed: engine.Verdict) -> str:
    names = []
    if computed.no_targets:
        names.append("no_targets")
    if computed.all_targets_unstable:
        names.append("all_targets_unstable")
    if computed.confounded:
        names.append("confounded")
    if computed.mixed_sources:
        names.append("mixed_sources")
    return ",".join(names) or "none"


def store_verdict(
    conn: sqlite3.Connection, product_id: int, computed: engine.Verdict
) -> int | None:
    """Replace this product/window's row; NEED_CHECKIN is a transient state."""
    if computed.outcome not in PERSISTED_OUTCOMES:
        return None
    payload = json.dumps(asdict(computed), ensure_ascii=False)
    conn.execute(
        "DELETE FROM verdicts WHERE product_id = ? AND check_window = ?",
        (product_id, computed.window),
    )
    cursor = conn.execute(
        "INSERT INTO verdicts (product_id, check_window, outcome, payload_json, "
        "computed_at) VALUES (?, ?, ?, ?, ?)",
        (
            product_id,
            computed.window,
            computed.outcome,
            payload,
            usage.utc_now_iso(),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid or 0)


def compute_for_product(
    conn: sqlite3.Connection, product_id: int, today: date | None = None
) -> engine.Verdict | None:
    """Load, compute, log and store one product's verdict."""
    row = conn.execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if row is None:
        return None
    product = dict(row)
    person_id = int(product["person_id"])
    captures = _load_captures(conn, person_id)
    bands = noise.get_bands(person_id, conn=conn)
    other_products = [
        dict(other)
        for other in conn.execute(
            "SELECT id, started_on, ended_on FROM products "
            "WHERE person_id = ? AND id != ?",
            (person_id, product_id),
        ).fetchall()
    ]
    computed = engine.compute_verdict(
        product,
        captures,
        bands,
        other_products,
        today or usage.guatemala_day(),
    )
    logs.log_event(
        "verdict.computed",
        product_id=product_id,
        outcome=computed.outcome,
        flags=_flags(computed),
    )
    store_verdict(conn, product_id, computed)
    return computed
