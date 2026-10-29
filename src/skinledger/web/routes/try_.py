"""Shared-link 'try it' flow behind the invite code (P06)."""

from __future__ import annotations

import hmac
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from skinledger import copy, guards, logs
from skinledger.config import get_settings
from skinledger.db import connect, db_path
from skinledger.web.forms import read_urlencoded_form
from skinledger.web.templating import templates

router = APIRouter()

MAX_INVITE_FAILURES = 10
INVITE_WINDOW_SECONDS = 3600

_invite_failures: dict[str, list[float]] = {}


def reset_invite_attempts() -> None:
    """Clear the in-memory limiter (tests start from a clean IP bucket)."""
    _invite_failures.clear()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _recent_failures(ip: str, now: float) -> list[float]:
    attempts = [
        stamp
        for stamp in _invite_failures.get(ip, [])
        if now - stamp < INVITE_WINDOW_SECONDS
    ]
    _invite_failures[ip] = attempts
    return attempts


def _demo_person_id() -> int | None:
    conn = connect(db_path())
    try:
        row = conn.execute(
            "SELECT id FROM persons WHERE is_demo_public = 1 ORDER BY id LIMIT 1"
        ).fetchone()
        return int(row["id"]) if row is not None else None
    finally:
        conn.close()


@router.get("/try", response_class=HTMLResponse)
async def try_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "try.html", {"error": None, "demo_person_id": _demo_person_id()}
    )


@router.post("/try", response_class=HTMLResponse)
async def submit_invite(request: Request):
    settings = get_settings()
    form = await read_urlencoded_form(request)
    code = str(form.get("invite_code") or "").strip()
    current = settings.invite_code.get_secret_value()

    if current and hmac.compare_digest(code, current):
        logs.log_event("invite.ok", http_status=303)
        response = RedirectResponse("/people/new", status_code=303)
        guards.set_invite_cookie(response, current)
        return response

    ip = _client_ip(request)
    now = time.monotonic()
    failures = _recent_failures(ip, now)
    if len(failures) >= MAX_INVITE_FAILURES:
        logs.log_event(
            "invite.failed",
            level="warning",
            count=len(failures),
            http_status=429,
        )
        raise HTTPException(status_code=429, detail=copy.TOO_MANY_INVITE_ATTEMPTS)
    failures.append(now)
    logs.log_event(
        "invite.failed",
        level="info",
        count=len(failures),
        http_status=400,
    )
    return templates.TemplateResponse(
        request,
        "try.html",
        {"error": copy.INVALID_INVITE, "demo_person_id": _demo_person_id()},
        status_code=400,
    )
