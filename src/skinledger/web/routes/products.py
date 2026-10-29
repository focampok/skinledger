"""Product log CRUD (P09): generic name, category, dates and target aspects."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from skinledger import copy, guards, logs, noise, usage
from skinledger.aspects import ASPECT_LABELS, NUMERIC_ASPECTS
from skinledger.db import connect, db_path
from skinledger.web import banners
from skinledger.web.forms import read_urlencoded_form_all
from skinledger.web.templating import templates

router = APIRouter()

CATEGORIES = (
    "cleanser",
    "serum",
    "moisturizer",
    "sunscreen",
    "exfoliant",
    "retinoid",
    "eye cream",
    "other",
)
MAX_TARGETS = 4
MAX_NAME = 80
DATA_LABEL = "REAL"


def _authorized_person_read(
    conn: sqlite3.Connection, request: Request, person_id: int
) -> sqlite3.Row:
    """Owner/admin, or anyone for the read-only public demo; 404 otherwise."""
    person = guards.authorize_person_read(conn, request, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found.")
    return person


def _authorized_person_write(
    conn: sqlite3.Connection, request: Request, person_id: int
) -> sqlite3.Row:
    """Owner or admin; the public demo is read-only (403)."""
    person = guards.authorize_person(conn, request, person_id)
    if person is None:
        if guards.demo_person(conn, person_id) is not None:
            raise HTTPException(status_code=403, detail=copy.DEMO_READ_ONLY)
        raise HTTPException(status_code=404, detail="Person not found.")
    if person["is_demo_public"] and not guards.is_admin_request(request):
        raise HTTPException(status_code=403, detail=copy.DEMO_READ_ONLY)
    return person


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request", "").lower() == "true"


def _parse_targets(raw: object) -> list[str]:
    """Tolerant JSON parse of a product's stored target aspects."""
    try:
        values = json.loads(str(raw or "[]"))
    except (TypeError, ValueError):
        return []
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value) in NUMERIC_ASPECTS]


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _aspect_choices(
    conn: sqlite3.Connection, person_id: int
) -> list[dict[str, object]]:
    """The 15 numeric checkboxes, flagged through noise.get_bands only."""
    bands = noise.get_bands(person_id, conn=conn)
    return [
        {
            "key": aspect,
            "label": ASPECT_LABELS[aspect],
            "unstable": bool((bands.get(aspect) or {}).get("unstable")),
        }
        for aspect in NUMERIC_ASPECTS
    ]


def _default_form(today: str) -> dict[str, object]:
    return {
        "name": "",
        "category": "serum",
        "started_on": today,
        "ended_on": "",
        "targets": [],
    }


def _read_form(form: dict[str, list[str]]) -> tuple[dict[str, object], str | None]:
    """Validate the submitted fields; returns the values to re-render and an error."""
    name = (form.get("name") or [""])[-1].strip()
    category = (form.get("category") or [""])[-1].strip().lower()
    started_raw = (form.get("started_on") or [""])[-1].strip()
    ended_raw = (form.get("ended_on") or [""])[-1].strip()
    targets = list(
        dict.fromkeys(
            value.strip()
            for value in form.get("target_aspects", [])
            if value.strip()
        )
    )
    values: dict[str, object] = {
        "name": name,
        "category": category,
        "started_on": started_raw or usage.guatemala_today(),
        "ended_on": ended_raw,
        "targets": targets,
    }

    if not name:
        return values, copy.PRODUCT_NAME_REQUIRED
    if len(name) > MAX_NAME:
        return values, copy.PRODUCT_NAME_TOO_LONG
    if category not in CATEGORIES:
        return values, copy.PRODUCT_CATEGORY_INVALID
    started = _parse_date(str(values["started_on"]))
    if started is None:
        return values, copy.PRODUCT_DATE_INVALID
    if ended_raw:
        ended = _parse_date(ended_raw)
        if ended is None:
            return values, copy.PRODUCT_DATE_INVALID
        if ended < started:
            return values, copy.PRODUCT_DATE_ORDER
    if not targets:
        return values, copy.PRODUCT_TARGETS_REQUIRED
    if len(targets) > MAX_TARGETS:
        return values, copy.PRODUCT_TOO_MANY_TARGETS
    if any(target not in NUMERIC_ASPECTS for target in targets):
        return values, copy.PRODUCT_UNKNOWN_TARGET
    return values, None


def _checkin_notice(started_on: str) -> str:
    """The two check-in dates derived from the product start (plan §12 windows)."""
    started = date.fromisoformat(started_on)
    day_14 = (started + timedelta(days=14)).isoformat()
    day_28 = (started + timedelta(days=28)).isoformat()
    return (
        "Check-ins: day 14 (between days 12–20) on "
        f"{day_14} and day 28 (26–35) on {day_28}."
    )


def _product_rows(
    conn: sqlite3.Connection, person_id: int, today: str
) -> list[dict[str, object]]:
    """Active products first, then newest start; each with its elapsed days."""
    rows = conn.execute(
        "SELECT id, name, category, started_on, ended_on, target_aspects, data_label "
        "FROM products WHERE person_id = ? "
        "ORDER BY ended_on IS NOT NULL, started_on DESC, id DESC",
        (person_id,),
    ).fetchall()
    products: list[dict[str, object]] = []
    for row in rows:
        started = date.fromisoformat(row["started_on"])
        ended_on = row["ended_on"]
        end = date.fromisoformat(ended_on) if ended_on else date.fromisoformat(today)
        products.append(
            {
                "id": int(row["id"]),
                "name": row["name"],
                "category": row["category"],
                "category_label": str(row["category"]).title(),
                "started_on": row["started_on"],
                "ended_on": ended_on,
                "active": not ended_on,
                "targets": [
                    {"key": aspect, "label": ASPECT_LABELS[aspect]}
                    for aspect in _parse_targets(row["target_aspects"])
                ],
                "days_elapsed": max(0, (end - started).days),
                "checkin_14": (started + timedelta(days=14)).isoformat(),
                "checkin_28": (started + timedelta(days=28)).isoformat(),
                "data_label": row["data_label"],
            }
        )
    return products


def _page_context(
    conn: sqlite3.Connection,
    person: sqlite3.Row,
    *,
    can_write: bool,
    demo_banner: str | None = None,
    notice: str | None = None,
    error: str | None = None,
    values: dict[str, object] | None = None,
) -> dict[str, object]:
    today = usage.guatemala_today()
    return {
        "person": dict(person),
        "can_write": can_write,
        "demo_banner": demo_banner,
        "products": _product_rows(conn, int(person["id"]), today),
        "categories": [
            {"key": category, "label": category.title()} for category in CATEGORIES
        ],
        "aspects": _aspect_choices(conn, int(person["id"])),
        "form": values or _default_form(today),
        "notice": notice,
        "error": error,
        "name_placeholder": copy.PRODUCT_NAME_PLACEHOLDER,
        "name_note": copy.PRODUCT_NAME_NOTE,
        "unstable_hint": copy.PRODUCT_UNSTABLE_HINT,
    }


@router.get("/people/{person_id}/products", response_class=HTMLResponse)
async def products_page(
    request: Request,
    person_id: int,
    created: int | None = None,
    ended: int | None = None,
) -> HTMLResponse:
    conn = connect(db_path())
    try:
        person = _authorized_person_read(conn, request, person_id)
        admin = guards.is_admin_request(request)
        can_write = not person["is_demo_public"] or admin
        demo_banner = banners.for_person(conn, person)
        notice = None
        if created is not None:
            row = conn.execute(
                "SELECT started_on FROM products WHERE id = ? AND person_id = ?",
                (created, person_id),
            ).fetchone()
            if row is not None:
                notice = _checkin_notice(row["started_on"])
        if ended is not None:
            row = conn.execute(
                "SELECT ended_on FROM products WHERE id = ? AND person_id = ?",
                (ended, person_id),
            ).fetchone()
            if row is not None and row["ended_on"]:
                notice = f"Product ended on {row['ended_on']}."
        context = _page_context(
            conn,
            person,
            can_write=can_write,
            demo_banner=demo_banner,
            notice=notice,
        )
    finally:
        conn.close()
    return templates.TemplateResponse(request, "products.html", context)


@router.post("/people/{person_id}/products")
async def create_product(request: Request, person_id: int):
    conn = connect(db_path())
    try:
        person = _authorized_person_write(conn, request, person_id)
        values, error = _read_form(await read_urlencoded_form_all(request))
        if error is not None:
            context = _page_context(
                conn,
                person,
                can_write=True,
                demo_banner=banners.for_person(conn, person),
                error=error,
                values=values,
            )
            if _is_htmx(request):
                return templates.TemplateResponse(
                    request, "products_list.html", context
                )
            return templates.TemplateResponse(
                request, "products.html", context, status_code=400
            )

        cursor = conn.execute(
            "INSERT INTO products (person_id, name, category, started_on, ended_on, "
            "target_aspects, data_label) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                person_id,
                values["name"],
                values["category"],
                values["started_on"],
                values["ended_on"] or None,
                json.dumps(values["targets"]),
                DATA_LABEL,
            ),
        )
        conn.commit()
        product_id = int(cursor.lastrowid or 0)
        logs.log_event("product.created", person_id=person_id, product_id=product_id)

        if _is_htmx(request):
            context = _page_context(
                conn,
                person,
                can_write=True,
                demo_banner=banners.for_person(conn, person),
                notice=_checkin_notice(str(values["started_on"])),
            )
            return templates.TemplateResponse(
                request, "products_list.html", context
            )
    finally:
        conn.close()
    return RedirectResponse(
        f"/people/{person_id}/products?created={product_id}", status_code=303
    )


@router.post("/people/{person_id}/products/{product_id}/end")
async def end_product(request: Request, person_id: int, product_id: int):
    conn = connect(db_path())
    try:
        person = _authorized_person_write(conn, request, person_id)
        row = conn.execute(
            "SELECT id, ended_on FROM products WHERE id = ? AND person_id = ?",
            (product_id, person_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found.")

        if row["ended_on"]:
            notice = f"Product already ended on {row['ended_on']}."
        else:
            today = usage.guatemala_today()
            conn.execute(
                "UPDATE products SET ended_on = ? WHERE id = ? AND person_id = ?",
                (today, product_id, person_id),
            )
            conn.commit()
            logs.log_event("product.ended", person_id=person_id, product_id=product_id)
            notice = f"Product ended on {today}."

        if _is_htmx(request):
            context = _page_context(
                conn,
                person,
                can_write=True,
                demo_banner=banners.for_person(conn, person),
                notice=notice,
            )
            return templates.TemplateResponse(
                request, "products_list.html", context
            )
    finally:
        conn.close()
    return RedirectResponse(
        f"/people/{person_id}/products?ended={product_id}", status_code=303
    )
