"""Profiles, consent (18+), shared-link entry and delete (P06)."""

from __future__ import annotations

import logging
import shutil

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from skinledger import copy, guards, logs, pipeline, usage
from skinledger.config import get_settings
from skinledger.db import connect, db_path
from skinledger.web.forms import read_urlencoded_form
from skinledger.web.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_DISPLAY_NAME = 80


def _owner_for(request: Request) -> tuple[str, bool]:
    token = guards.owner_token_from_request(request)
    if token:
        return token, False
    return guards.new_owner_token(), True


def _render(
    request: Request,
    template: str,
    context: dict,
    *,
    token: str | None = None,
    is_new: bool = False,
    status_code: int = 200,
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request, template, context, status_code=status_code
    )
    if is_new and token:
        guards.set_owner_cookie(response, token)
    return response


def _redirect(url: str, token: str, is_new: bool) -> RedirectResponse:
    response = RedirectResponse(url, status_code=303)
    if is_new:
        guards.set_owner_cookie(response, token)
    return response


@router.get("/people", response_class=HTMLResponse)
async def people_page(request: Request) -> HTMLResponse:
    token, is_new = _owner_for(request)
    admin = guards.is_admin_request(request)
    conn = connect(db_path())
    try:
        if admin:
            rows = conn.execute("SELECT * FROM persons ORDER BY is_demo_public, id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM persons WHERE owner_token_hash = ? OR is_demo_public = 1 "
                "ORDER BY is_demo_public, id",
                (guards.owner_token_hash(token),),
            ).fetchall()
    finally:
        conn.close()
    return _render(
        request,
        "people.html",
        {"persons": [dict(row) for row in rows], "admin": admin},
        token=token,
        is_new=is_new,
    )


@router.get("/people/new", response_class=HTMLResponse)
async def new_person_page(request: Request) -> HTMLResponse:
    token, is_new = _owner_for(request)
    return _render(
        request,
        "person_new.html",
        {"error": None},
        token=token,
        is_new=is_new,
    )


@router.post("/people/new", response_class=HTMLResponse)
async def create_person(request: Request):
    token = guards.owner_token_from_request(request)
    is_new = token is None
    if token is None:
        token = guards.new_owner_token()
    form = await read_urlencoded_form(request)
    name = str(form.get("display_name") or "").strip()

    if not name:
        return _render(
            request,
            "person_new.html",
            {"error": copy.NAME_REQUIRED},
            token=token,
            is_new=is_new,
            status_code=400,
        )
    if len(name) > MAX_DISPLAY_NAME:
        return _render(
            request,
            "person_new.html",
            {"error": f"Please use {MAX_DISPLAY_NAME} characters or fewer."},
            token=token,
            is_new=is_new,
            status_code=400,
        )

    conn = connect(db_path())
    try:
        cursor = conn.execute(
            "INSERT INTO persons (display_name, owner_token_hash) VALUES (?, ?)",
            (name, guards.owner_token_hash(token)),
        )
        conn.commit()
        person_id = int(cursor.lastrowid or 0)
        logs.log_event("person.created", person_id=person_id)
    finally:
        conn.close()
    return _redirect(f"/people/{person_id}/consent", token, is_new)


@router.get("/people/{person_id}/consent", response_class=HTMLResponse)
async def consent_page(request: Request, person_id: int) -> HTMLResponse:
    conn = connect(db_path())
    try:
        person = guards.authorize_person(conn, request, person_id)
    finally:
        conn.close()
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found.")
    admin = guards.is_admin_request(request)
    if person["is_demo_public"] and not admin:
        raise HTTPException(status_code=403, detail=copy.DEMO_READ_ONLY)
    return templates.TemplateResponse(
        request,
        "consent.html",
        {"person": dict(person), "error": None, "consent_version": copy.CONSENT_VERSION},
    )


@router.post("/people/{person_id}/consent", response_class=HTMLResponse)
async def accept_consent(request: Request, person_id: int):
    conn = connect(db_path())
    try:
        person = guards.authorize_person(conn, request, person_id)
        if person is None:
            raise HTTPException(status_code=404, detail="Person not found.")
        admin = guards.is_admin_request(request)
        if person["is_demo_public"] and not admin:
            raise HTTPException(status_code=403, detail=copy.DEMO_READ_ONLY)

        form = await read_urlencoded_form(request)
        adult_confirmed = form.get("adult_confirmed") is not None
        agreed = form.get("agree") is not None
        if not (adult_confirmed and agreed):
            return templates.TemplateResponse(
                request,
                "consent.html",
                {
                    "person": dict(person),
                    "error": copy.CONSENT_BOXES_REQUIRED,
                    "consent_version": copy.CONSENT_VERSION,
                },
                status_code=400,
            )

        conn.execute(
            "INSERT INTO consents "
            "(person_id, consent_version, adult_confirmed, accepted_at) "
            "VALUES (?, ?, 1, ?)",
            (person_id, copy.CONSENT_VERSION, usage.utc_now_iso()),
        )
        conn.commit()
        logs.log_event(
            "consent.accepted",
            person_id=person_id,
            consent_version=copy.CONSENT_VERSION,
        )
    finally:
        conn.close()
    return RedirectResponse("/people", status_code=303)


@router.get("/people/{person_id}/delete", response_class=HTMLResponse)
async def delete_person_page(request: Request, person_id: int) -> HTMLResponse:
    conn = connect(db_path())
    try:
        person = guards.authorize_person(conn, request, person_id)
    finally:
        conn.close()
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found.")
    admin = guards.is_admin_request(request)
    if person["is_demo_public"] and not admin:
        raise HTTPException(status_code=403, detail=copy.DEMO_READ_ONLY)
    return templates.TemplateResponse(
        request, "delete_person.html", {"person": dict(person), "error": None}
    )


@router.post("/people/{person_id}/delete", response_class=HTMLResponse)
async def delete_person(request: Request, person_id: int) -> HTMLResponse:
    settings = get_settings()
    conn = connect(db_path())
    try:
        person = guards.authorize_person(conn, request, person_id)
        if person is None:
            raise HTTPException(status_code=404, detail="Person not found.")
        admin = guards.is_admin_request(request)
        if person["is_demo_public"] and not admin:
            raise HTTPException(status_code=403, detail=copy.DEMO_READ_ONLY)

        form = await read_urlencoded_form(request)
        confirmation = str(form.get("confirm_name") or "").strip()
        if confirmation != person["display_name"]:
            return templates.TemplateResponse(
                request,
                "delete_person.html",
                {"person": dict(person), "error": copy.DELETE_CONFIRM_MISMATCH},
                status_code=400,
            )

        async with pipeline.analysis_io_lock():
            conn.execute("DELETE FROM persons WHERE id = ?", (person_id,))
            conn.commit()

            folder = settings.data_dir / "masks" / str(person_id)
            if folder.exists():
                shutil.rmtree(folder)
            if folder.exists():
                raise HTTPException(
                    status_code=500, detail="Could not remove the mask files."
                )

            remaining = _remaining_rows(conn, person_id)
            if remaining:
                logger.error(
                    "Person %s still has rows after delete: %s", person_id, remaining
                )
                raise HTTPException(status_code=500, detail="Delete did not complete.")
    finally:
        conn.close()

    logs.log_event("person.deleted", person_id=person_id)
    # UNVERIFIED: YouCam's exact deletion channel for an uploaded photo.
    return templates.TemplateResponse(
        request, "person_deleted.html", {"message": copy.DELETED_MESSAGE}
    )


def _remaining_rows(conn, person_id: int) -> dict[str, int]:
    remaining: dict[str, int] = {}
    for table in ("consents", "captures", "noise_bands", "products"):
        count = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE person_id = ?", (person_id,)
        ).fetchone()[0]
        if count:
            remaining[table] = int(count)
    return remaining
