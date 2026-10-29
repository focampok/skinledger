"""Per-aspect timeline page and series JSON (P08).

Bands are read only through skinledger.noise: this module never recomputes them and
never redefines NOISE_FLOOR or UNSTABLE_BAND. Chart data contains raw_score only;
ui_score is discarded at parse time and never exists in the database.
"""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from skinledger import copy, guards, logs, noise
from skinledger.aspects import ASPECT_LABELS, NUMERIC_ASPECTS
from skinledger.db import connect, db_path
from skinledger.web.templating import templates
from skinledger.youcam import SKIN_TYPE_REGIONS

router = APIRouter()

# The skin-type chip prefers the whole-face value, then the zone values.
SKIN_TYPE_KEYS = tuple(f"skin_type_{region}" for region in SKIN_TYPE_REGIONS)


def _authorized_person(
    conn: sqlite3.Connection, request: Request, person_id: int
) -> sqlite3.Row:
    """The same guard as /people/{id}/baseline: owner or admin, 404 otherwise."""
    person = guards.authorize_person(conn, request, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found.")
    if person["is_demo_public"] and not guards.is_admin_request(request):
        raise HTTPException(status_code=403, detail=copy.DEMO_READ_ONLY)
    return person


def _captures(conn: sqlite3.Connection, person_id: int) -> list[sqlite3.Row]:
    """Successful captures only: failed or unfinished analyses have no points."""
    return conn.execute(
        "SELECT id, captured_at, data_label, source FROM captures "
        "WHERE person_id = ? AND status = 'success' ORDER BY captured_at, id",
        (person_id,),
    ).fetchall()


def _scores(
    conn: sqlite3.Connection, capture_ids: list[int]
) -> dict[int, dict[str, sqlite3.Row]]:
    if not capture_ids:
        return {}
    placeholders = ", ".join("?" for _ in capture_ids)
    rows = conn.execute(
        "SELECT capture_id, aspect, raw_score, value_text FROM aspect_scores "
        f"WHERE capture_id IN ({placeholders})",
        tuple(capture_ids),
    ).fetchall()
    stored: dict[int, dict[str, sqlite3.Row]] = {}
    for row in rows:
        stored.setdefault(int(row["capture_id"]), {})[row["aspect"]] = row
    return stored


def _parse_targets(raw: object) -> list[str]:
    """Tolerant JSON parse; unknown aspects are ignored and order is preserved."""
    try:
        values = json.loads(str(raw or "[]"))
    except (TypeError, ValueError):
        return []
    if not isinstance(values, list):
        return []
    targets: list[str] = []
    for value in values:
        aspect = str(value)
        if aspect in NUMERIC_ASPECTS and aspect not in targets:
            targets.append(aspect)
    return targets


def _products(conn: sqlite3.Connection, person_id: int) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT name, category, started_on, ended_on, target_aspects, data_label "
        "FROM products WHERE person_id = ? ORDER BY started_on, id",
        (person_id,),
    ).fetchall()
    return [
        {
            "name": row["name"],
            "category": row["category"],
            "started_on": row["started_on"],
            "ended_on": row["ended_on"],
            "target_aspects": _parse_targets(row["target_aspects"]),
            "data_label": row["data_label"],
            "active": row["ended_on"] in (None, ""),
        }
        for row in rows
    ]


def _baselines(report: noise.BandReport | None) -> dict[str, float]:
    """The band's centre: the mean of both day-1 captures, rounded to 0.1."""
    if report is None:
        return {}
    centres: dict[str, float] = {}
    for aspect, (first, second) in report.scores.items():
        if first is None or second is None:
            continue
        centres[aspect] = round((float(first) + float(second)) / 2, 1)
    return centres


def _is_unstable(bands: dict[str, dict[str, object]], aspect: str) -> bool:
    entry = bands.get(aspect)
    return bool(entry is not None and entry["unstable"])


def _aspect_order(
    products: list[dict[str, object]], bands: dict[str, dict[str, object]]
) -> list[tuple[str, str]]:
    """Targets of active products first, stable aspects next, unstable ones last."""
    unstable = [aspect for aspect in NUMERIC_ASPECTS if _is_unstable(bands, aspect)]
    unstable_set = set(unstable)
    targets: list[str] = []
    for product in products:
        if not product["active"]:
            continue
        for aspect in product["target_aspects"]:
            if aspect not in unstable_set and aspect not in targets:
                targets.append(str(aspect))
    target_set = set(targets)
    stable = [
        aspect
        for aspect in NUMERIC_ASPECTS
        if aspect not in unstable_set and aspect not in target_set
    ]
    return (
        [(aspect, "target") for aspect in targets]
        + [(aspect, "stable") for aspect in stable]
        + [(aspect, "unstable") for aspect in unstable]
    )


def _skin_type(
    captures: list[sqlite3.Row], scores: dict[int, dict[str, sqlite3.Row]]
) -> dict[str, object] | None:
    """The latest successful capture's skin-type value, newest capture first."""
    for capture in reversed(captures):
        stored = scores.get(int(capture["id"]), {})
        for key in SKIN_TYPE_KEYS:
            row = stored.get(key)
            if row is not None and row["value_text"]:
                return {
                    "value": row["value_text"],
                    "t": capture["captured_at"],
                    "data_label": capture["data_label"],
                    "capture_id": int(capture["id"]),
                }
    return None


def build_series(conn: sqlite3.Connection, person_id: int) -> dict[str, object]:
    """Everything the timeline page and its JSON endpoint need, in final card order."""
    bands = noise.get_bands(person_id, conn=conn)
    report = noise.read_band_report(person_id, conn=conn)
    centres = _baselines(report)
    captures = _captures(conn, person_id)
    scores = _scores(conn, [int(capture["id"]) for capture in captures])
    products = _products(conn, person_id)

    aspects: list[dict[str, object]] = []
    for aspect, group in _aspect_order(products, bands):
        points: list[dict[str, object]] = []
        for capture in captures:
            row = scores.get(int(capture["id"]), {}).get(aspect)
            if row is None or row["raw_score"] is None:
                continue
            points.append(
                {
                    "t": capture["captured_at"],
                    "raw_score": float(row["raw_score"]),
                    "data_label": capture["data_label"],
                    "source": capture["source"],
                    "capture_id": int(capture["id"]),
                }
            )
        entry = bands.get(aspect)
        aspects.append(
            {
                "aspect": aspect,
                "label": ASPECT_LABELS[aspect],
                "group": group,
                "band": float(entry["band"]) if entry is not None else None,
                "floor_applied": (
                    bool(entry["floor_applied"]) if entry is not None else None
                ),
                "unstable": _is_unstable(bands, aspect),
                "baseline": centres.get(aspect),
                "points": points,
            }
        )

    return {
        "person_id": person_id,
        "has_band": bool(bands),
        "aspects": aspects,
        "skin_type": _skin_type(captures, scores),
        "products": products,
    }


@router.get("/people/{person_id}/timeline", response_class=HTMLResponse)
async def timeline_page(request: Request, person_id: int) -> HTMLResponse:
    conn = connect(db_path())
    try:
        person = _authorized_person(conn, request, person_id)
        person_data = dict(person)
        series = build_series(conn, person_id)
    finally:
        conn.close()

    logs.log_event(
        "timeline.viewed", person_id=person_id, aspect_count=len(series["aspects"])
    )
    return templates.TemplateResponse(
        request,
        "timeline.html",
        {
            "person": person_data,
            "cards": series["aspects"],
            "has_band": series["has_band"],
            "skin_type": series["skin_type"],
            "timeline_title": copy.TIMELINE_TITLE,
            "band_legend": copy.TIMELINE_BAND_LEGEND,
            "unstable_chip": copy.TIMELINE_UNSTABLE_CHIP,
            "unstable_note": copy.TIMELINE_UNSTABLE_NOTE,
            "no_band_yet": copy.NO_BAND_YET,
        },
    )


@router.get("/api/people/{person_id}/series")
async def people_series(request: Request, person_id: int) -> JSONResponse:
    conn = connect(db_path())
    try:
        _authorized_person(conn, request, person_id)
        series = build_series(conn, person_id)
    finally:
        conn.close()
    return JSONResponse(series, headers={"Cache-Control": "no-store"})
