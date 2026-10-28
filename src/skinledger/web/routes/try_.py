"""Shared-link 'try it' flow behind the invite code (P06)."""

from __future__ import annotations

import hmac
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from skinledger import copy, guards
from skinledger.config import get_settings
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


@router.get("/try", response_class=HTMLResponse)
async def try_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "try.html", {"error": None})


@router.post("/try", response_class=HTMLResponse)
async def submit_invite(request: Request):
    settings = get_settings()
    form = await read_urlencoded_form(request)
    code = str(form.get("invite_code") or "").strip()
    current = settings.invite_code.get_secret_value()

    if current and hmac.compare_digest(code, current):
        response = RedirectResponse("/people/new", status_code=303)
        guards.set_invite_cookie(response, current)
        return response

    ip = _client_ip(request)
    now = time.monotonic()
    if len(_recent_failures(ip, now)) >= MAX_INVITE_FAILURES:
        raise HTTPException(status_code=429, detail=copy.TOO_MANY_INVITE_ATTEMPTS)
    _recent_failures(ip, now).append(now)
    return templates.TemplateResponse(
        request, "try.html", {"error": copy.INVALID_INVITE}, status_code=400
    )
