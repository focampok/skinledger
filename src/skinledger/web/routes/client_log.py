"""Client log bridge: phone diagnostics land in the server log without cookies or images."""

from __future__ import annotations

import json
import re
import time

from fastapi import APIRouter, HTTPException, Request, Response

from skinledger import guards, logs

router = APIRouter()

MAX_CLIENT_LOG_BYTES = 2048
MAX_EVENTS_PER_MINUTE = 30
WINDOW_SECONDS = 60.0

_EVENT_RE = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_LEVELS = {
    "debug": "debug",
    "info": "info",
    "warning": "warning",
    "warn": "warning",
    "error": "error",
}

_events: dict[str, list[float]] = {}


def reset_client_log_attempts() -> None:
    """Clear the in-memory limiter (tests start from clean buckets)."""
    _events.clear()


def _rate_key(request: Request) -> str:
    """Buckets keyed by the signed owner cookie hash, or by IP when there is none."""
    token = guards.owner_token_from_request(request)
    if token:
        return "owner:" + guards.owner_token_hash(token)
    client = request.client.host if request.client else "unknown"
    return "ip:" + client


def _allowed(key: str, now: float) -> bool:
    recent = [stamp for stamp in _events.get(key, []) if now - stamp < WINDOW_SECONDS]
    if len(recent) >= MAX_EVENTS_PER_MINUTE:
        _events[key] = recent
        return False
    recent.append(now)
    _events[key] = recent
    return True


async def _read_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_CLIENT_LOG_BYTES:
                raise HTTPException(status_code=413, detail="Client log payload is too large.")
        except ValueError:
            pass

    buffer = bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer) > MAX_CLIENT_LOG_BYTES:
            raise HTTPException(status_code=413, detail="Client log payload is too large.")
    return bytes(buffer)


@router.post("/api/client-log", status_code=204)
async def client_log(request: Request) -> Response:
    """Accept a small diagnostic event from the browser; no auth, rate-limited per owner."""
    if not _allowed(_rate_key(request), time.monotonic()):
        raise HTTPException(status_code=429, detail="Too many client log events.")

    body = await _read_body(request)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid client log payload.") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid client log payload.")

    event = payload.get("event")
    if not isinstance(event, str) or not _EVENT_RE.fullmatch(event):
        raise HTTPException(status_code=400, detail="Invalid client log event.")

    level = payload.get("level", "info")
    if not isinstance(level, str) or level.lower() not in _LEVELS:
        raise HTTPException(status_code=400, detail="Invalid client log level.")

    detail = payload.get("detail", "")
    if not isinstance(detail, str):
        raise HTTPException(status_code=400, detail="Invalid client log detail.")
    if len(detail) > 1024:
        detail = detail[:1024]

    logs.log_event(f"client.{event}", level=_LEVELS[level.lower()], detail=detail)
    return Response(status_code=204)
