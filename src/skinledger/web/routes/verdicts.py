"""Verdict screen (P11): compute on read and render the frozen outcome."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from skinledger import copy, guards, logs, verdict_store
from skinledger.aspects import ASPECT_LABELS
from skinledger.db import connect, db_path
from skinledger.verdict import TargetResult, Verdict
from skinledger.web import banners
from skinledger.web.templating import templates

router = APIRouter()


def _authorized_product(
    conn: sqlite3.Connection, request: Request, product_id: int
) -> tuple[sqlite3.Row, sqlite3.Row]:
    """Owner/admin, or anyone for the read-only public demo; 404 otherwise."""
    product = conn.execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    person = guards.authorize_person_read(conn, request, int(product["person_id"]))
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found.")
    return product, person


def _score(value: float | None) -> str:
    return "—" if value is None else f"{float(value):.1f}"


def _arrow(delta: float) -> str:
    return "↑" if delta > 0 else "↓" if delta < 0 else "→"


def _change(delta: float | None) -> str:
    if delta is None:
        return "—"
    value = float(delta)
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f} {_arrow(value)}"


def _outside(target: TargetResult) -> str:
    if target.status == "unstable":
        return copy.VERDICT_UNSTABLE_NOT_USED
    if target.status in ("improved", "worse"):
        return "✓"
    if target.status == "within_noise":
        return "—"
    if target.status == "no_band":
        return copy.VERDICT_NO_BAND_CELL
    if target.status == "pending":
        return copy.VERDICT_PENDING_CELL
    return copy.VERDICT_NO_SCORE


def _outside_state(target: TargetResult) -> str:
    """Mobile chip state: a measured change, within noise, or not comparable."""
    if target.status in ("improved", "worse"):
        return "outside"
    if target.status == "within_noise":
        return "within"
    return "other"


def _direction_label(target: TargetResult) -> str:
    """The verdict engine treats higher raw_score as better; mirror it in words.

    Source: YouCam AI Skin Analysis docs, Inputs & Outputs: raw_score is 1-100 and
    "a higher score indicates healthier and more aesthetically pleasing skin condition".
    """
    if target.status == "improved":
        return copy.VERDICT_DIRECTION_IMPROVED
    if target.status == "worse":
        return copy.VERDICT_DIRECTION_WORSE
    return ""


def _outside_plain(target: TargetResult) -> str:
    """Words for the mobile chip; the table keeps the compact symbol."""
    state = _outside_state(target)
    if state == "outside":
        return copy.VERDICT_OUTSIDE_NOISE
    if state == "within":
        return copy.VERDICT_WITHIN_NOISE
    return _outside(target)


def _target_rows(computed: Verdict) -> list[dict[str, object]]:
    return [
        {
            "aspect": target.aspect,
            "label": ASPECT_LABELS.get(target.aspect, target.aspect),
            "baseline": _score(target.baseline),
            "checkin": _score(target.checkin),
            "change": _change(target.delta),
            "band": "—" if target.band is None else f"{float(target.band):.1f}",
            "band_display": "—" if target.band is None else f"±{float(target.band):.1f}",
            "outside": _outside(target),
            "outside_plain": _outside_plain(target),
            "outside_state": _outside_state(target),
            "direction_label": _direction_label(target),
            "unstable": target.status == "unstable",
        }
        for target in computed.targets
    ]


def _top_rows(computed: Verdict) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for change in computed.top_changes:
        delta = float(change["delta"])
        if change["band"] is None:
            outside = copy.VERDICT_NO_BAND_CELL
        elif change["outside_band"]:
            outside = copy.VERDICT_OUTSIDE_NOISE
        else:
            outside = copy.VERDICT_WITHIN_NOISE
        band = change["band"]
        rows.append(
            {
                "label": change["label"],
                "delta": f"{'+' if delta > 0 else ''}{delta:.1f}",
                "arrow": _arrow(delta),
                "outside": outside,
                "direction_label": (
                    copy.VERDICT_DIRECTION_IMPROVED
                    if change["status"] == "improved"
                    else copy.VERDICT_DIRECTION_WORSE
                    if change["status"] == "worse"
                    else ""
                ),
                "band": None if band is None else f"±{float(band):.1f}",
            }
        )
    return rows


def _mask_rows(computed: Verdict) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for pair in computed.mask_pairs:
        rows.append(
            {
                "label": ASPECT_LABELS.get(str(pair["aspect"]), str(pair["aspect"])),
                "before_capture_id": int(pair["before_capture_id"]),
                "after_capture_id": int(pair["after_capture_id"]),
                "before_file": PurePosixPath(str(pair["before_path"])).name,
                "after_file": PurePosixPath(str(pair["after_path"])).name,
            }
        )
    return rows


@router.get("/products/{product_id}/verdict", response_class=HTMLResponse)
async def verdict_page(request: Request, product_id: int) -> HTMLResponse:
    conn = connect(db_path())
    try:
        product, person = _authorized_product(conn, request, product_id)
        product_data = dict(product)
        person_data = dict(person)
        demo_banner = banners.for_person(conn, person)
        can_write = not person["is_demo_public"] or guards.is_admin_request(request)
        computed = verdict_store.compute_for_product(conn, product_id)
        if computed is None:
            raise HTTPException(status_code=404, detail="Product not found.")
    finally:
        conn.close()

    logs.log_event(
        "verdict.viewed", product_id=product_id, outcome=computed.outcome
    )

    window_label = (
        copy.VERDICT_DAY_14 if computed.window == "d14" else copy.VERDICT_DAY_28
    )
    window_days = 14 if computed.window == "d14" else 28
    started = date.fromisoformat(product_data["started_on"])
    window_date = computed.checkin_date or (
        started + timedelta(days=window_days)
    ).isoformat()

    return templates.TemplateResponse(
        request,
        "verdict.html",
        {
            "product": product_data,
            "person": person_data,
            "verdict": computed,
            "demo_banner": demo_banner,
            "can_write": can_write,
            "outcome_label": copy.verdict_outcome_label(computed.outcome),
            "window_label": window_label,
            "window_date": window_date,
            "target_rows": _target_rows(computed),
            "top_change_rows": _top_rows(computed),
            "mask_rows": _mask_rows(computed),
            "unstable_rows": [
                {
                    "label": ASPECT_LABELS.get(
                        str(target["aspect"]), str(target["aspect"])
                    ),
                    "band": target["band"],
                }
                for target in computed.unstable_targets
            ],
        },
    )
