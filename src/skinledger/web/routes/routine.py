"""AM/PM routine and shopping list page (P12)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from skinledger import copy, guards, logs, noise, shopping, verdict_store
from skinledger import routine as routine_engine
from skinledger.db import connect, db_path
from skinledger.verdict import KEEP
from skinledger.web.templating import templates

router = APIRouter()


def _authorized_person(
    conn: sqlite3.Connection, request: Request, person_id: int
) -> sqlite3.Row:
    """The same guard as /people/{id}/timeline: owner or admin, 404 otherwise."""
    person = guards.authorize_person(conn, request, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found.")
    if person["is_demo_public"] and not guards.is_admin_request(request):
        raise HTTPException(status_code=403, detail=copy.DEMO_READ_ONLY)
    return person


def _latest_capture(
    conn: sqlite3.Connection, person_id: int
) -> dict[str, object] | None:
    """The latest successful capture and its raw scores (never ui_score)."""
    row = conn.execute(
        "SELECT id, captured_at, data_label FROM captures "
        "WHERE person_id = ? AND status = 'success' "
        "ORDER BY captured_at DESC, id DESC LIMIT 1",
        (person_id,),
    ).fetchone()
    if row is None:
        return None
    scores = {
        score["aspect"]: float(score["raw_score"])
        for score in conn.execute(
            "SELECT aspect, raw_score FROM aspect_scores "
            "WHERE capture_id = ? AND raw_score IS NOT NULL",
            (row["id"],),
        )
    }
    return {
        "id": int(row["id"]),
        "captured_at": row["captured_at"],
        "data_label": row["data_label"],
        "scores": scores,
    }


def _active_categories(conn: sqlite3.Connection, person_id: int) -> list[str]:
    return [
        row["category"]
        for row in conn.execute(
            "SELECT category FROM products WHERE person_id = ? AND ended_on IS NULL",
            (person_id,),
        )
    ]


def _keep_using(conn: sqlite3.Connection, person_id: int) -> list[str]:
    """Active products whose current verdict is KEEP."""
    names: list[str] = []
    products = conn.execute(
        "SELECT id, name FROM products WHERE person_id = ? AND ended_on IS NULL "
        "ORDER BY started_on, id",
        (person_id,),
    ).fetchall()
    for product in products:
        computed = verdict_store.compute_for_product(conn, int(product["id"]))
        if computed is not None and computed.outcome == KEEP:
            names.append(str(product["name"]))
    return names


@router.get("/people/{person_id}/routine", response_class=HTMLResponse)
async def routine_page(request: Request, person_id: int) -> HTMLResponse:
    conn = connect(db_path())
    try:
        person = _authorized_person(conn, request, person_id)
        person_data = dict(person)
        capture = _latest_capture(conn, person_id)
        bands = noise.get_bands(person_id, conn=conn)
        active_categories = _active_categories(conn, person_id)
        keep_using = _keep_using(conn, person_id)
    finally:
        conn.close()

    plan = routine_engine.build_routine(capture, bands)
    shopping_items = shopping.build_shopping_list(
        [*plan.am, *plan.pm], active_categories
    )
    aspects = ",".join(item.aspect for item in plan.lowest) or "none"
    logs.log_event("routine.viewed", person_id=person_id, aspects=aspects)

    return templates.TemplateResponse(
        request,
        "routine.html",
        {
            "person": person_data,
            "routine": plan,
            "shopping_items": shopping_items,
            "keep_using": keep_using,
        },
    )
