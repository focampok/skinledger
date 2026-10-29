"""Day-1 noise bands: per-aspect max(|A - B|, 3.0) from two baseline captures (P07).

NOISE_FLOOR and UNSTABLE_BAND are product heuristics, not YouCam figures: the only
honest estimate of a person's measurement noise is their own back-to-back captures.
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass, field

from skinledger import usage
from skinledger.aspects import NUMERIC_ASPECTS
from skinledger.db import connect, db_path, init_db
from skinledger.youcam import SKIN_TYPE_REGIONS

# Product heuristic, not a YouCam figure: below this every change is treated as noise.
NOISE_FLOOR = 3.0
# Product heuristic, not a YouCam figure: above this an aspect cannot be judged at all.
UNSTABLE_BAND = 10.0

MIXED_SOURCE_NOTE = "Captured different ways; the band may be wider than usual."
SKIN_TYPE_NOTE = "Skin type differed between captures."

_BAND_QUERY = (
    "SELECT aspect, band, floor_applied FROM noise_bands WHERE person_id = ? ORDER BY aspect"
)


@dataclass(slots=True)
class BandReport:
    """One baseline pair: its bands, both captures' scores and the notes they produce."""

    person_id: int
    a_capture_id: int
    b_capture_id: int
    data_label: str
    scores: dict[str, tuple[float | None, float | None]] = field(default_factory=dict)
    bands: dict[str, dict[str, object]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def is_unstable(band: float) -> bool:
    """True when two back-to-back captures moved too much to judge that aspect."""
    return band > UNSTABLE_BAND


def compute_band(
    person_id: int, conn: sqlite3.Connection | None = None
) -> BandReport | None:
    """Compute and store the band from the person's most recent baseline pair.

    Needs two successful captures marked is_baseline_pair; returns None otherwise.
    Storing replaces every band the person had, so a new pair never mixes with an old one.
    """
    own_connection = conn is None
    if conn is None:
        conn = connect(db_path())
    try:
        pair = _latest_pair(conn, person_id)
        if pair is None:
            return None
        first, second = pair
        scores_a = _scores(conn, first["id"])
        scores_b = _scores(conn, second["id"])
        report = BandReport(
            person_id=person_id,
            a_capture_id=int(first["id"]),
            b_capture_id=int(second["id"]),
            data_label=str(second["data_label"]),
            scores=_score_pairs(scores_a, scores_b),
            bands={},
            notes=_notes(first, second, scores_a, scores_b),
        )
        report.bands = _compute_bands(report.scores)
        _store(conn, report)
        conn.commit()
        return report
    finally:
        if own_connection:
            conn.close()


def get_bands(
    person_id: int, conn: sqlite3.Connection | None = None
) -> dict[str, dict[str, object]]:
    """{aspect: {"band", "floor_applied", "unstable"}} for the stored day-1 band.

    P08's verdict engine must ignore aspects where "unstable" is true: their movement
    between two back-to-back captures is too large for a 14/28-day comparison to say
    anything. An aspect with no row here has no band and therefore no verdict either.
    """
    own_connection = conn is None
    if conn is None:
        conn = connect(db_path())
    try:
        rows = conn.execute(_BAND_QUERY, (person_id,)).fetchall()
    finally:
        if own_connection:
            conn.close()
    return {
        row["aspect"]: {
            "band": float(row["band"]),
            "floor_applied": bool(row["floor_applied"]),
            "unstable": is_unstable(float(row["band"])),
        }
        for row in rows
    }


def has_band(person_id: int, conn: sqlite3.Connection | None = None) -> bool:
    """True once a band has been stored for this person."""
    own_connection = conn is None
    if conn is None:
        conn = connect(db_path())
    try:
        row = conn.execute(
            "SELECT 1 FROM noise_bands WHERE person_id = ? LIMIT 1", (person_id,)
        ).fetchone()
        return row is not None
    finally:
        if own_connection:
            conn.close()


def read_band_report(
    person_id: int, conn: sqlite3.Connection | None = None
) -> BandReport | None:
    """The stored band plus both captures' scores, for the baseline page."""
    own_connection = conn is None
    if conn is None:
        conn = connect(db_path())
    try:
        bands = get_bands(person_id, conn=conn)
        if not bands:
            return None
        pair = conn.execute(
            "SELECT a_capture_id, b_capture_id FROM noise_bands WHERE person_id = ? LIMIT 1",
            (person_id,),
        ).fetchone()
        first = conn.execute(
            "SELECT * FROM captures WHERE id = ?", (pair["a_capture_id"],)
        ).fetchone()
        second = conn.execute(
            "SELECT * FROM captures WHERE id = ?", (pair["b_capture_id"],)
        ).fetchone()
        if first is None or second is None:
            return None
        scores_a = _scores(conn, first["id"])
        scores_b = _scores(conn, second["id"])
        return BandReport(
            person_id=person_id,
            a_capture_id=int(first["id"]),
            b_capture_id=int(second["id"]),
            data_label=str(second["data_label"]),
            scores=_score_pairs(scores_a, scores_b),
            bands=bands,
            notes=_notes(first, second, scores_a, scores_b),
        )
    finally:
        if own_connection:
            conn.close()


def recompute_all() -> int:
    """Recompute every profile with two successful baseline captures; returns how many."""
    init_db()
    conn = connect(db_path())
    try:
        person_ids = [
            int(row["person_id"])
            for row in conn.execute(
                "SELECT DISTINCT person_id FROM captures "
                "WHERE is_baseline_pair = 1 AND status = 'success'"
            ).fetchall()
        ]
        updated = 0
        for person_id in person_ids:
            if compute_band(person_id, conn=conn) is not None:
                updated += 1
        return updated
    finally:
        conn.close()


def _latest_pair(
    conn: sqlite3.Connection, person_id: int
) -> tuple[sqlite3.Row, sqlite3.Row] | None:
    """The two most recent successful baseline captures, earlier first."""
    rows = conn.execute(
        "SELECT * FROM captures WHERE person_id = ? AND is_baseline_pair = 1 "
        "AND status = 'success' ORDER BY captured_at DESC, id DESC LIMIT 2",
        (person_id,),
    ).fetchall()
    if len(rows) < 2:
        return None
    return rows[1], rows[0]


def _scores(conn: sqlite3.Connection, capture_id: int) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        "SELECT aspect, raw_score, value_text FROM aspect_scores WHERE capture_id = ?",
        (capture_id,),
    ).fetchall()
    return {row["aspect"]: row for row in rows}


def _score_pairs(
    scores_a: dict[str, sqlite3.Row], scores_b: dict[str, sqlite3.Row]
) -> dict[str, tuple[float | None, float | None]]:
    """Both captures' raw score per numeric aspect; None when the aspect is missing."""
    pairs: dict[str, tuple[float | None, float | None]] = {}
    for aspect in NUMERIC_ASPECTS:
        first = scores_a.get(aspect)
        second = scores_b.get(aspect)
        pairs[aspect] = (
            None if first is None else first["raw_score"],
            None if second is None else second["raw_score"],
        )
    return pairs


def _band(diff: float) -> tuple[float, bool]:
    """The band for one aspect: the measured difference, floored and rounded to 0.1."""
    return round(max(diff, NOISE_FLOOR), 1), diff < NOISE_FLOOR


def _compute_bands(
    pairs: dict[str, tuple[float | None, float | None]],
) -> dict[str, dict[str, object]]:
    bands: dict[str, dict[str, object]] = {}
    for aspect, (first, second) in pairs.items():
        if first is None or second is None:
            continue
        band, floor_applied = _band(abs(float(first) - float(second)))
        bands[aspect] = {
            "band": band,
            "floor_applied": floor_applied,
            "unstable": is_unstable(band),
        }
    return bands


def _notes(
    first: sqlite3.Row,
    second: sqlite3.Row,
    scores_a: dict[str, sqlite3.Row],
    scores_b: dict[str, sqlite3.Row],
) -> list[str]:
    notes: list[str] = []
    if {first["source"], second["source"]} == {"camera_kit", "upload"}:
        notes.append(MIXED_SOURCE_NOTE)
    # skin_type is categorical, so it has no band: a changed region is only a warning.
    for region in SKIN_TYPE_REGIONS:
        key = f"skin_type_{region}"
        left = scores_a.get(key)
        right = scores_b.get(key)
        left_value = left["value_text"] if left is not None else None
        right_value = right["value_text"] if right is not None else None
        if left_value is not None and right_value is not None and left_value != right_value:
            notes.append(SKIN_TYPE_NOTE)
            break
    return notes


def _store(conn: sqlite3.Connection, report: BandReport) -> None:
    """Replace every band for this person with the new pair's bands."""
    now = usage.utc_now_iso()
    conn.execute("DELETE FROM noise_bands WHERE person_id = ?", (report.person_id,))
    for aspect, values in report.bands.items():
        conn.execute(
            "INSERT INTO noise_bands (person_id, aspect, band, a_capture_id, b_capture_id, "
            "floor_applied, computed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                report.person_id,
                aspect,
                values["band"],
                report.a_capture_id,
                report.b_capture_id,
                int(bool(values["floor_applied"])),
                now,
            ),
        )


def main(argv: list[str] | None = None) -> int:
    """CLI: `python -m skinledger.noise --recompute-all`."""
    parser = argparse.ArgumentParser(
        description="Recompute SkinLedger day-1 noise bands from stored captures."
    )
    parser.add_argument(
        "--recompute-all",
        action="store_true",
        help="recompute the band for every profile with two successful baseline captures",
    )
    args = parser.parse_args(argv)
    if not args.recompute_all:
        parser.error("pass --recompute-all")
    updated = recompute_all()
    print(f"Recomputed noise bands for {updated} profile(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
